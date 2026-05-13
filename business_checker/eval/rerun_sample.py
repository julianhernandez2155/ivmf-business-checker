"""Re-run the AI on a specific eval sample (60 rows) with cache bypassed.

Used during prompt-iteration cycles to regenerate predictions on the same rows
the human labeled, so we can score new prompt against old labels.

Usage (CLI):
    python -m eval.rerun_sample \\
        --sample eval/datasets/bmosg_v1_eval_sample.csv \\
        --input-xlsx ../data/BMOSG_All_Businesses.xlsx \\
        --workers 3 \\
        --out eval/datasets/bmosg_v1_iteration_1_predictions.csv

Outputs a CSV with the same columns as the labeled sample plus refreshed
predicted_status / predicted_confidence / predicted_evidence / predicted_citations.
The human_label / human_justification / reviewed_at columns are preserved
unchanged from the input — they are the ground truth.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import openpyxl
import pandas as pd
from dotenv import load_dotenv

# Make tools importable when running as `python -m eval.rerun_sample`
# from the business_checker directory.
sys.path.insert(0, str(Path(__file__).parent.parent))
from tools.check_business import (  # noqa: E402
    check_business,
    check_business_3pass,
    check_business_with_verification,
)
from tools.pipeline_configs import (  # noqa: E402
    PIPELINE_NAMES,
    PipelineConfig,
    get_pipeline_config,
)

BRANCH_A_PIPELINE_NAMES = ("v14_branch_a1", "v14_branch_a2")

logger = logging.getLogger(__name__)


def _load_input_rows(xlsx_path: Path) -> dict[int, dict]:
    """Read the input xlsx into a dict keyed by 1-based row_index.

    row_index in the eval sample is 1-based and skips the header (so the
    first business is row_index=2). This matches the convention the
    Business Checker runner uses when writing checkpoints.

    Returns:
        Dict {row_index: {name, website, city, state, metadata}}.
        `metadata` is a BusinessMetadata instance with optional fields
        populated from the spreadsheet.
    """
    from tools.business_metadata import BusinessMetadata, _coerce_to_date
    from tools.columns import detect_columns

    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.rows)
    wb.close()

    raw_headers = [c.value for c in rows[0]]
    col_map = detect_columns(raw_headers)

    if col_map.get("name") is None:
        raise ValueError(f"Could not find a name column in {xlsx_path}")

    def _cell_str(row: tuple, key: str) -> str:
        idx = col_map.get(key)
        if idx is None or idx >= len(row):
            return ""
        v = row[idx].value
        return str(v).strip() if v is not None else ""

    def _cell_date(row: tuple, key: str):
        idx = col_map.get(key)
        if idx is None or idx >= len(row):
            return None
        return _coerce_to_date(row[idx].value)

    out: dict[int, dict] = {}
    for sheet_idx, row in enumerate(rows[1:], start=2):
        first = _cell_str(row, "first_name")
        last = _cell_str(row, "last_name")
        owner = " ".join(p for p in (first, last) if p) or None

        metadata = BusinessMetadata(
            owner_name=owner,
            category=_cell_str(row, "category") or None,
            description=_cell_str(row, "description") or None,
            date_added=_cell_date(row, "date_added"),
            date_verified=_cell_date(row, "date_verified"),
        )
        out[sheet_idx] = {
            "name": _cell_str(row, "name"),
            "website": _cell_str(row, "website"),
            "city": _cell_str(row, "city"),
            "state": _cell_str(row, "state"),
            "metadata": metadata,
        }
    return out


def rerun_sample(
    sample_csv: Path,
    input_xlsx: Path,
    api_key: str,
    config: PipelineConfig,
    workers: int = 3,
    verify_flagged: bool = False,
    three_pass: bool = False,
    anthropic_api_key: str | None = None,
) -> pd.DataFrame:
    """Re-run the AI on every row in `sample_csv`, bypass cache, return new
    predictions.

    Args:
        sample_csv: Path to a labeled sample CSV (output of eval/sample.py).
        input_xlsx: Path to the original input xlsx (for fresh field lookup).
        api_key: PERPLEXITY_API_KEY.
        config: PipelineConfig that pins every toggle (since iter 13). Eval
            and production share the same configs so they cannot silently
            diverge.
        workers: Concurrent worker count.
        verify_flagged: CLI override on top of `config.verify_flagged`.
        three_pass: Run 3 passes per row instead of single or verified.

    Returns:
        DataFrame with the same shape as input but with refreshed predicted_*
        fields and a new "rerun_checked_at" timestamp column.
    """
    df = pd.read_csv(sample_csv, dtype={"predicted_confidence": str})
    input_lookup = _load_input_rows(input_xlsx)

    refreshed_rows: list[dict] = []
    rerun_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    effective_verify_flagged = bool(config.verify_flagged or verify_flagged)
    pipeline_fp = config.fingerprint()
    logger.info("Pipeline: %s (fp=%s) — %s", config.name, pipeline_fp, config.as_log_dict())

    def process(row_dict: dict) -> dict:
        idx = int(row_dict["row_index"])
        input_data = input_lookup.get(idx, {})
        # Prefer xlsx-fresh values; fall back to whatever's in the sample CSV.
        name = input_data.get("name") or str(row_dict.get("name", ""))
        website = input_data.get("website") or str(row_dict.get("website", ""))
        city = input_data.get("city") or str(row_dict.get("city", ""))
        state = input_data.get("state") or str(row_dict.get("state", ""))
        # Only pass metadata into the checker when the active config opts in.
        extracted_metadata = input_data.get("metadata")
        metadata = extracted_metadata if config.use_metadata else None

        if config.name in BRANCH_A_PIPELINE_NAMES:
            # iter-14 Branch A1 / A2: v11 gather → Sonnet adjudicator.
            # Inherits v11 toggle set verbatim; the only thing that changes
            # is the final-verdict source. A2 also scrapes top 3 citations.
            if not anthropic_api_key:
                raise ValueError(
                    "v14_branch_a* pipelines require ANTHROPIC_API_KEY in .env."
                )
            from tools.check_business_branch_a import check_business_branch_a
            result = check_business_branch_a(
                perplexity_api_key=api_key,
                anthropic_api_key=anthropic_api_key,
                name=name,
                website=website,
                city=city,
                state=state,
                enable_citation_scraping=(config.name == "v14_branch_a2"),
                metadata=None,  # A1/A2 honor v11 use_metadata=False
                pipeline_fingerprint=pipeline_fp,
            )
        elif three_pass:
            # 3-pass mode does not currently support FB recency or metadata
            # injection (the cost would triple). It still honors
            # marketplace-residue and the pipeline fingerprint.
            result = check_business_3pass(
                api_key=api_key,
                name=name,
                website=website,
                city=city,
                state=state,
                cache=None,
                use_rule_scorer=config.use_rule_scorer,
                use_marketplace_residue=config.use_marketplace_residue,
                pipeline_fingerprint=pipeline_fp,
            )
        elif effective_verify_flagged:
            result = check_business_with_verification(
                api_key=api_key,
                name=name,
                website=website,
                city=city,
                state=state,
                cache=None,
                use_rule_scorer=config.use_rule_scorer,
                use_facebook_recency=config.use_facebook_recency,
                use_instagram_fallback=config.use_instagram_fallback,
                use_marketplace_residue=config.use_marketplace_residue,
                metadata=metadata,
                pipeline_fingerprint=pipeline_fp,
            )
        else:
            result = check_business(
                api_key=api_key,
                name=name,
                website=website,
                city=city,
                state=state,
                cache=None,  # Force fresh API call — bypass cache for prompt iteration
                use_rule_scorer=config.use_rule_scorer,
                use_facebook_recency=config.use_facebook_recency,
                use_instagram_fallback=config.use_instagram_fallback,
                use_marketplace_residue=config.use_marketplace_residue,
                metadata=metadata,
                pipeline_fingerprint=pipeline_fp,
            )

        return {
            **row_dict,
            "predicted_status": result["status"],
            "predicted_confidence": result["confidence"],
            "predicted_evidence_full": result["evidence"],  # full evidence including sources
            "predicted_citations": ", ".join(result.get("citations", [])),
            "rerun_checked_at": rerun_ts,
            "rerun_cost_usd": result.get("cost_usd", 0.0),
            "rerun_error": result.get("error") or "",
            "rerun_verifier_ran": result.get("verifier_ran", False),
            "rerun_requires_review": result.get("requires_review", False),
            "rerun_pass1_status": result.get("pass1_status", ""),
            "rerun_pass2_status": result.get("pass2_status", ""),
            "rerun_pass3_status": result.get("pass3_status", ""),
        }

    row_dicts = df.to_dict(orient="records")
    total = len(row_dicts)
    logger.info("Re-running %d rows with %d workers (cache bypassed)", total, workers)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(process, r): r for r in row_dicts}
        for i, future in enumerate(as_completed(futures), start=1):
            try:
                refreshed_rows.append(future.result())
                if i % 5 == 0 or i == total:
                    logger.info("  %d / %d done", i, total)
            except Exception as e:
                row = futures[future]
                logger.error("Row %s failed: %s", row.get("row_index"), e)
                refreshed_rows.append({
                    **row,
                    "predicted_status": "Uncertain",
                    "predicted_confidence": "0",
                    "predicted_evidence_full": f"Re-run error: {e}",
                    "predicted_citations": "",
                    "rerun_checked_at": rerun_ts,
                    "rerun_cost_usd": 0.0,
                    "rerun_error": str(e),
                })

    out_df = pd.DataFrame(refreshed_rows)
    # Preserve original sample row order
    out_df = out_df.sort_values("row_index").reset_index(drop=True)

    # Split predicted_evidence_full into evidence + citations text columns,
    # matching the sample-format produced by eval/sample.py.
    def split_evidence(raw: str) -> tuple[str, str]:
        sep = " | Sources: "
        if sep in str(raw):
            left, right = str(raw).split(sep, maxsplit=1)
            return left.strip(), right.strip()
        return str(raw).strip(), ""

    ev_split = out_df["predicted_evidence_full"].apply(split_evidence)
    out_df["predicted_evidence"] = ev_split.apply(lambda t: t[0])
    # Prefer freshly-emitted citations field; fall back to suffix-extracted
    out_df["predicted_citations"] = out_df.apply(
        lambda r: r["predicted_citations"] or split_evidence(r["predicted_evidence_full"])[1],
        axis=1,
    )

    # Preserve column order similar to original sample CSV
    preserve_cols = [
        "row_index", "name", "website", "city", "state",
        "predicted_status", "predicted_confidence",
        "predicted_evidence", "predicted_citations",
        "predicted_checked_at",
        "human_label", "human_justification", "reviewed_at",
        "rerun_checked_at", "rerun_cost_usd", "rerun_error",
        # Verify-flagged / 3-pass mode columns
        "rerun_verifier_ran", "rerun_requires_review",
        "rerun_pass1_status", "rerun_pass2_status", "rerun_pass3_status",
    ]
    cols = [c for c in preserve_cols if c in out_df.columns]
    return out_df[cols]


class _RemovedFlagAction(argparse.Action):
    """Argparse action that hard-errors with a migration message.

    Used for `--enable-facebook-recency` and `--enable-instagram-fallback`,
    which were removed in iter 13. Operators who copy/paste old commands
    get an immediate, actionable error pointing at `--pipeline`.
    """

    def __call__(self, parser, namespace, values, option_string=None):
        parser.error(
            f"{option_string} was removed in iter 13. "
            f"Use --pipeline {{{','.join(PIPELINE_NAMES)}}} instead. "
            f"See docs/2026-05-12-iter13-stabilization-plan.md."
        )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m eval.rerun_sample",
        description="Re-run the AI on a labeled eval sample, bypassing cache.",
    )
    parser.add_argument("--sample", required=True, type=Path,
                        help="Path to labeled sample CSV (e.g., bmosg_v1_eval_sample.csv)")
    parser.add_argument("--input-xlsx", required=True, type=Path,
                        help="Path to the original input .xlsx")
    parser.add_argument(
        "--pipeline", required=True, choices=PIPELINE_NAMES,
        help="Named pipeline configuration. Required since iter 13 — "
             "the same configs as run_checker.py, so eval cannot drift "
             f"from production. Valid: {', '.join(PIPELINE_NAMES)}.",
    )
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--out", required=True, type=Path,
                        help="Output CSV path for refreshed predictions")
    parser.add_argument("--verify-flagged", action="store_true",
                        help="Force check_business_with_verification on top of "
                             "the pipeline's verify_flagged setting (most pipelines "
                             "already enable this).")
    parser.add_argument("--3pass", dest="three_pass", action="store_true",
                        help="Use check_business_3pass — runs 3 passes on EVERY row, "
                             "auto-trusts only when all 3 agree. 3x cost.")
    # Removed in iter 13. Kept registered so old commands get a clear error.
    parser.add_argument(
        "--enable-facebook-recency", action=_RemovedFlagAction, nargs=0,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--enable-instagram-fallback", action=_RemovedFlagAction, nargs=0,
        help=argparse.SUPPRESS,
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s",
                        datefmt="%H:%M:%S")
    # Load .env from the project root (one level above eval/)
    load_dotenv(Path(__file__).parent.parent / ".env")
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        print("ERROR: PERPLEXITY_API_KEY not set in .env", file=sys.stderr)
        sys.exit(1)

    args = _build_parser().parse_args(argv)
    if args.verify_flagged and args.three_pass:
        print("ERROR: --verify-flagged and --3pass are mutually exclusive.", file=sys.stderr)
        sys.exit(1)
    config = get_pipeline_config(args.pipeline)
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if config.name in BRANCH_A_PIPELINE_NAMES and not anthropic_key:
        print("ERROR: --pipeline v14_branch_a* requires ANTHROPIC_API_KEY in .env",
              file=sys.stderr)
        sys.exit(1)
    out_df = rerun_sample(
        sample_csv=args.sample,
        input_xlsx=args.input_xlsx,
        api_key=api_key,
        config=config,
        workers=args.workers,
        verify_flagged=args.verify_flagged,
        three_pass=args.three_pass,
        anthropic_api_key=anthropic_key,
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(args.out, index=False)

    total_cost = float(out_df["rerun_cost_usd"].sum())
    err_count = int((out_df["rerun_error"].astype(str) != "").sum())
    print(f"\nRe-run complete.")
    print(f"  Rows:        {len(out_df)}")
    print(f"  Total cost:  ${total_cost:.4f}")
    print(f"  Errors:      {err_count}")
    print(f"  Output:      {args.out}")
    if args.verify_flagged and "rerun_verifier_ran" in out_df.columns:
        verified = int(out_df["rerun_verifier_ran"].sum())
        print(f"  2nd-pass runs: {verified} ({verified/len(out_df)*100:.1f}%)")


if __name__ == "__main__":
    main(sys.argv[1:])
