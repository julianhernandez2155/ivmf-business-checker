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

logger = logging.getLogger(__name__)


def _load_input_rows(xlsx_path: Path) -> dict[int, dict]:
    """Read the input xlsx into a dict keyed by 1-based row_index.

    row_index in the eval sample is 1-based and skips the header (so the
    first business is row_index=2). This matches the convention the
    Business Checker runner uses when writing checkpoints.

    Returns:
        Dict {row_index: {name, website, city, state}}.
    """
    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.rows)
    wb.close()

    headers = [str(c.value or "").strip().lower() for c in rows[0]]

    def find_col(*candidates: str) -> int | None:
        for cand in candidates:
            for idx, h in enumerate(headers):
                if cand in h:
                    return idx
        return None

    name_idx = find_col("name", "business name", "company")
    website_idx = find_col("website", "url", "site", "link")
    city_idx = find_col("city", "town", "municipality")
    state_idx = find_col("state", "province", "region")

    if name_idx is None:
        raise ValueError(f"Could not find a name column in {xlsx_path}")

    out: dict[int, dict] = {}
    for sheet_idx, row in enumerate(rows[1:], start=2):
        out[sheet_idx] = {
            "name": str(row[name_idx].value or "").strip() if name_idx is not None else "",
            "website": str(row[website_idx].value or "").strip() if website_idx is not None else "",
            "city": str(row[city_idx].value or "").strip() if city_idx is not None else "",
            "state": str(row[state_idx].value or "").strip() if state_idx is not None else "",
        }
    return out


def rerun_sample(
    sample_csv: Path,
    input_xlsx: Path,
    api_key: str,
    workers: int = 3,
    verify_flagged: bool = False,
    three_pass: bool = False,
) -> pd.DataFrame:
    """Re-run the AI on every row in `sample_csv`, bypass cache, return new
    predictions.

    Args:
        sample_csv: Path to a labeled sample CSV (output of eval/sample.py).
        input_xlsx: Path to the original input xlsx (for fresh field lookup).
        api_key: PERPLEXITY_API_KEY.
        workers: Concurrent worker count.

    Returns:
        DataFrame with the same shape as input but with refreshed predicted_*
        fields and a new "rerun_checked_at" timestamp column.
    """
    df = pd.read_csv(sample_csv, dtype={"predicted_confidence": str})
    input_lookup = _load_input_rows(input_xlsx)

    refreshed_rows: list[dict] = []
    rerun_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def process(row_dict: dict) -> dict:
        idx = int(row_dict["row_index"])
        input_data = input_lookup.get(idx, {})
        # Prefer xlsx-fresh values; fall back to whatever's in the sample CSV.
        name = input_data.get("name") or str(row_dict.get("name", ""))
        website = input_data.get("website") or str(row_dict.get("website", ""))
        city = input_data.get("city") or str(row_dict.get("city", ""))
        state = input_data.get("state") or str(row_dict.get("state", ""))

        if three_pass:
            result = check_business_3pass(
                api_key=api_key,
                name=name,
                website=website,
                city=city,
                state=state,
                cache=None,
            )
        elif verify_flagged:
            result = check_business_with_verification(
                api_key=api_key,
                name=name,
                website=website,
                city=city,
                state=state,
                cache=None,
            )
        else:
            result = check_business(
                api_key=api_key,
                name=name,
                website=website,
                city=city,
                state=state,
                cache=None,  # Force fresh API call — bypass cache for prompt iteration
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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m eval.rerun_sample",
        description="Re-run the AI on a labeled eval sample, bypassing cache.",
    )
    parser.add_argument("--sample", required=True, type=Path,
                        help="Path to labeled sample CSV (e.g., bmosg_v1_eval_sample.csv)")
    parser.add_argument("--input-xlsx", required=True, type=Path,
                        help="Path to the original input .xlsx")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--out", required=True, type=Path,
                        help="Output CSV path for refreshed predictions")
    parser.add_argument("--verify-flagged", action="store_true",
                        help="Use check_business_with_verification — runs a 2nd "
                             "pass on rows flagged for review and merges results.")
    parser.add_argument("--3pass", dest="three_pass", action="store_true",
                        help="Use check_business_3pass — runs 3 passes on EVERY row, "
                             "auto-trusts only when all 3 agree. 3x cost.")
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
    out_df = rerun_sample(
        sample_csv=args.sample,
        input_xlsx=args.input_xlsx,
        api_key=api_key,
        workers=args.workers,
        verify_flagged=args.verify_flagged,
        three_pass=args.three_pass,
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
