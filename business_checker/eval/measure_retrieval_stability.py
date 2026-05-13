"""Phase 0 — Perplexity retrieval-stability measurement (iter 14 spike).

Runs the v11 pipeline twice over the same 60-row eval sample (cache bypassed)
and classifies each row into one of four drift buckets based on whether the
citation set and the verdict changed between pass 1 and pass 2.

Outputs
-------
- predictions_pass1.csv / predictions_pass2.csv — full rerun outputs (same
  shape as `eval.rerun_sample`).
- pass_diff.csv — per-row diff with citation Jaccard, status comparison,
  confidence delta, and the drift bucket.
- iter14_phase0_retrieval_stability.md — one-page report with median Jaccard,
  bucket counts, the 10 most-divergent rows, all stable_drift rows enumerated,
  and the reasoning/retrieval/both classification.

Usage
-----
    python -m eval.measure_retrieval_stability \\
        --sample eval/datasets/bmosg_v1_eval_sample.csv \\
        --input-xlsx ../data/BMOSG_All_Businesses.xlsx \\
        --out-dir eval/reports/iter14_phase0 \\
        --workers 3

The script is deliberately small: it composes existing modules (rerun_sample,
pipeline_configs) and the row-level analysis is a single pure function so the
plan's bucket math is testable.

Plan reference: docs/2026-05-13-iter14-search-vs-reasoning-spike.md §Phase 0.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import median

import pandas as pd
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
from eval.rerun_sample import rerun_sample  # noqa: E402
from tools.pipeline_configs import get_pipeline_config  # noqa: E402

logger = logging.getLogger(__name__)

# Bucket thresholds from the plan:
#   - citation set is "stable" when Jaccard >= 0.80
#   - "reasoning-dominant" when stable_drift >= 25% of rows AND median Jaccard >= 0.65
#   - "retrieval-dominant" when (drift_drift + drift_stable) >= 50% AND median Jaccard < 0.50
JACCARD_STABLE_THRESHOLD = 0.80
REASONING_DOMINANT_DRIFT_PCT = 0.25
REASONING_DOMINANT_JACCARD_FLOOR = 0.65
RETRIEVAL_DOMINANT_DRIFT_PCT = 0.50
RETRIEVAL_DOMINANT_JACCARD_CEILING = 0.50


@dataclass(frozen=True)
class RowDiff:
    """Per-row comparison between pass 1 and pass 2."""

    row_index: int
    name: str
    status_pass1: str
    status_pass2: str
    confidence_pass1: str
    confidence_pass2: str
    citations_pass1: tuple[str, ...]
    citations_pass2: tuple[str, ...]
    jaccard: float
    citation_set_stable: bool
    verdict_changed: bool
    bucket: str  # stable_stable | stable_drift | drift_stable | drift_drift


def _parse_citations(raw: object) -> tuple[str, ...]:
    """Split a comma-separated citation string into a normalized tuple."""
    if raw is None:
        return ()
    text = str(raw).strip()
    if not text:
        return ()
    parts = [p.strip().rstrip("/").lower() for p in text.split(",") if p.strip()]
    return tuple(sorted(set(parts)))


def _jaccard(a: tuple[str, ...], b: tuple[str, ...]) -> float:
    """Jaccard similarity of two citation tuples. Empty/empty = 1.0."""
    set_a, set_b = set(a), set(b)
    if not set_a and not set_b:
        return 1.0
    union = set_a | set_b
    if not union:
        return 1.0
    return len(set_a & set_b) / len(union)


def _bucket(citation_stable: bool, verdict_changed: bool) -> str:
    if citation_stable and not verdict_changed:
        return "stable_stable"
    if citation_stable and verdict_changed:
        return "stable_drift"
    if not citation_stable and not verdict_changed:
        return "drift_stable"
    return "drift_drift"


def diff_runs(df1: pd.DataFrame, df2: pd.DataFrame) -> list[RowDiff]:
    """Join pass 1 and pass 2 on row_index and compute per-row drift bucket.

    Rows that errored in either pass (`rerun_error` non-empty) are excluded
    so a Perplexity 5xx in one pass does not get coded as "retrieval drift".
    """
    merged = df1.merge(
        df2,
        on="row_index",
        suffixes=("_p1", "_p2"),
        how="inner",
        validate="one_to_one",
    )

    diffs: list[RowDiff] = []
    for _, row in merged.iterrows():
        err_p1 = str(row.get("rerun_error_p1", "") or "").strip()
        err_p2 = str(row.get("rerun_error_p2", "") or "").strip()
        if err_p1 or err_p2:
            logger.warning(
                "Row %s excluded — error in %s",
                row["row_index"],
                "pass1" if err_p1 else "pass2",
            )
            continue

        citations1 = _parse_citations(row.get("predicted_citations_p1"))
        citations2 = _parse_citations(row.get("predicted_citations_p2"))
        jaccard = _jaccard(citations1, citations2)
        citation_stable = jaccard >= JACCARD_STABLE_THRESHOLD

        status1 = str(row.get("predicted_status_p1", "")).strip()
        status2 = str(row.get("predicted_status_p2", "")).strip()
        verdict_changed = status1 != status2

        diffs.append(
            RowDiff(
                row_index=int(row["row_index"]),
                name=str(row.get("name_p1") or row.get("name_p2") or ""),
                status_pass1=status1,
                status_pass2=status2,
                confidence_pass1=str(row.get("predicted_confidence_p1", "")),
                confidence_pass2=str(row.get("predicted_confidence_p2", "")),
                citations_pass1=citations1,
                citations_pass2=citations2,
                jaccard=jaccard,
                citation_set_stable=citation_stable,
                verdict_changed=verdict_changed,
                bucket=_bucket(citation_stable, verdict_changed),
            )
        )
    return diffs


def classify(diffs: list[RowDiff]) -> tuple[str, float, Counter]:
    """Apply the plan's classification rule to bucket counts + median Jaccard.

    Returns:
        (classification, median_jaccard, bucket_counts)
    """
    counts: Counter = Counter(d.bucket for d in diffs)
    total = len(diffs)
    if total == 0:
        return "insufficient_data", 0.0, counts

    med = median(d.jaccard for d in diffs)
    stable_drift_pct = counts["stable_drift"] / total
    retrieval_drift_pct = (counts["drift_drift"] + counts["drift_stable"]) / total

    if stable_drift_pct >= REASONING_DOMINANT_DRIFT_PCT and med >= REASONING_DOMINANT_JACCARD_FLOOR:
        return "reasoning-dominant", med, counts
    if retrieval_drift_pct >= RETRIEVAL_DOMINANT_DRIFT_PCT and med < RETRIEVAL_DOMINANT_JACCARD_CEILING:
        return "retrieval-dominant", med, counts
    return "both", med, counts


def _format_report(
    diffs: list[RowDiff],
    classification: str,
    median_jaccard: float,
    counts: Counter,
    cost_pass1: float,
    cost_pass2: float,
    pass1_ts: str,
    pass2_ts: str,
) -> str:
    """Render the Phase 0 markdown report."""
    total = len(diffs)
    top_divergent = sorted(diffs, key=lambda d: d.jaccard)[:10]
    stable_drift_rows = [d for d in diffs if d.bucket == "stable_drift"]

    def bucket_row(name: str, description: str) -> str:
        n = counts.get(name, 0)
        pct = (n / total * 100) if total else 0.0
        return f"| `{name}` | {n} | {pct:.1f}% | {description} |"

    lines: list[str] = []
    lines.append("# Iter 14 — Phase 0: Perplexity retrieval-stability report\n")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**Pipeline:** v11")
    lines.append(f"**Pass 1 ran at:** {pass1_ts}")
    lines.append(f"**Pass 2 ran at:** {pass2_ts}")
    lines.append(f"**Rows compared:** {total}")
    lines.append(f"**Total cost:** ${cost_pass1 + cost_pass2:.4f} (pass 1 ${cost_pass1:.4f} + pass 2 ${cost_pass2:.4f})\n")

    lines.append("## Headline\n")
    lines.append(f"- **Median citation-set Jaccard:** {median_jaccard:.3f}")
    lines.append(f"- **Classification:** **{classification}**\n")

    lines.append("## Drift buckets\n")
    lines.append("| Bucket | Count | % | Meaning |")
    lines.append("| --- | ---: | ---: | --- |")
    lines.append(bucket_row("stable_stable", "citations same (Jaccard ≥ 0.80), verdict same — reproducible row"))
    lines.append(bucket_row("stable_drift", "citations same, verdict CHANGED — **reasoning drift signal**"))
    lines.append(bucket_row("drift_drift", "citations changed AND verdict changed — retrieval may have caused it"))
    lines.append(bucket_row("drift_stable", "citations changed, verdict same — Perplexity robust to retrieval churn"))
    lines.append("")

    lines.append("## Classification rule applied\n")
    lines.append("Per the plan:")
    lines.append("- `reasoning-dominant` if `stable_drift` ≥ 25% of rows AND median Jaccard ≥ 0.65 → Branch A1 priority.")
    lines.append("- `retrieval-dominant` if (`drift_drift` + `drift_stable`) ≥ 50% AND median Jaccard < 0.50 → Branch B priority.")
    lines.append("- `both` otherwise → full sequence.\n")

    lines.append("## 10 most-divergent rows (lowest citation-set Jaccard)\n")
    lines.append("| row_index | name | jaccard | status p1 → p2 | bucket |")
    lines.append("| ---: | --- | ---: | --- | --- |")
    for d in top_divergent:
        verdict = f"{d.status_pass1} → {d.status_pass2}"
        lines.append(f"| {d.row_index} | {d.name} | {d.jaccard:.2f} | {verdict} | {d.bucket} |")
    lines.append("")

    lines.append(f"## `stable_drift` rows (n={len(stable_drift_rows)})\n")
    lines.append(
        "These are the cleanest evidence of reasoning drift — Perplexity saw\n"
        "the same URLs on both passes and emitted a different verdict.\n"
    )
    if stable_drift_rows:
        lines.append("| row_index | name | status p1 | status p2 | confidence p1 | confidence p2 |")
        lines.append("| ---: | --- | --- | --- | ---: | ---: |")
        for d in stable_drift_rows:
            lines.append(
                f"| {d.row_index} | {d.name} | {d.status_pass1} | {d.status_pass2} "
                f"| {d.confidence_pass1} | {d.confidence_pass2} |"
            )
    else:
        lines.append("_None — no reasoning-drift rows in this sample._")
    lines.append("")

    lines.append("## Checkpoint #1 — budget commitment\n")
    if classification == "reasoning-dominant":
        lines.append(
            "→ **A1 priority.** Branch A2 + B remain confirmatory; skip them only\n"
            "if budget is tight, and document why in the checkpoint #2 note.\n"
        )
    elif classification == "retrieval-dominant":
        lines.append(
            "→ **B priority.** Branch A1 still runs as a control. A2 conditional\n"
            "on checkpoint #2 variance.\n"
        )
    else:
        lines.append(
            "→ **Full sequence.** Phase 0 did not isolate a single dominant layer;\n"
            "the spike's side-by-side will decide.\n"
        )
    lines.append("Always proceed to Phase 1 — adjudicator + compare_configs N-input ext.\n")

    return "\n".join(lines)


def _diffs_to_dataframe(diffs: list[RowDiff]) -> pd.DataFrame:
    """Materialize the per-row diffs as a CSV-friendly DataFrame."""
    return pd.DataFrame(
        [
            {
                "row_index": d.row_index,
                "name": d.name,
                "status_pass1": d.status_pass1,
                "status_pass2": d.status_pass2,
                "confidence_pass1": d.confidence_pass1,
                "confidence_pass2": d.confidence_pass2,
                "citations_pass1": " | ".join(d.citations_pass1),
                "citations_pass2": " | ".join(d.citations_pass2),
                "jaccard": round(d.jaccard, 4),
                "citation_set_stable": d.citation_set_stable,
                "verdict_changed": d.verdict_changed,
                "bucket": d.bucket,
            }
            for d in diffs
        ]
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m eval.measure_retrieval_stability",
        description="Phase 0 — measure Perplexity retrieval-stability (iter 14 spike).",
    )
    parser.add_argument("--sample", required=True, type=Path,
                        help="Labeled sample CSV (e.g. eval/datasets/bmosg_v1_eval_sample.csv)")
    parser.add_argument("--input-xlsx", required=True, type=Path,
                        help="Original input xlsx (e.g. ../data/BMOSG_All_Businesses.xlsx)")
    parser.add_argument("--out-dir", required=True, type=Path,
                        help="Output directory (e.g. eval/reports/iter14_phase0)")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument(
        "--reuse-pass1", type=Path, default=None,
        help="Optional: skip pass 1 and reuse a previous predictions CSV at this path. "
             "Use when pass 1 has already run and the second pass needs a separate window.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s",
                        datefmt="%H:%M:%S")
    load_dotenv(Path(__file__).parent.parent / ".env")
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        print("ERROR: PERPLEXITY_API_KEY not set in .env", file=sys.stderr)
        sys.exit(1)

    args = _build_parser().parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    config = get_pipeline_config("v11")
    logger.info("Pipeline pinned: %s (fp=%s)", config.name, config.fingerprint())

    pass1_path = args.out_dir / "predictions_pass1.csv"
    pass2_path = args.out_dir / "predictions_pass2.csv"

    if args.reuse_pass1 is not None:
        logger.info("Reusing pass 1 predictions from %s", args.reuse_pass1)
        df1 = pd.read_csv(args.reuse_pass1, dtype={"predicted_confidence": str})
        # Mirror into the out-dir so the report has both CSVs colocated.
        df1.to_csv(pass1_path, index=False)
    else:
        logger.info("Pass 1 — fresh v11 run (cache bypassed)")
        df1 = rerun_sample(
            sample_csv=args.sample,
            input_xlsx=args.input_xlsx,
            api_key=api_key,
            config=config,
            workers=args.workers,
            verify_flagged=False,
            three_pass=False,
        )
        df1.to_csv(pass1_path, index=False)
        logger.info("Pass 1 written → %s", pass1_path)

    logger.info("Pass 2 — fresh v11 run (cache bypassed)")
    df2 = rerun_sample(
        sample_csv=args.sample,
        input_xlsx=args.input_xlsx,
        api_key=api_key,
        config=config,
        workers=args.workers,
        verify_flagged=False,
        three_pass=False,
    )
    df2.to_csv(pass2_path, index=False)
    logger.info("Pass 2 written → %s", pass2_path)

    diffs = diff_runs(df1, df2)
    classification, median_jaccard, counts = classify(diffs)

    diff_df = _diffs_to_dataframe(diffs)
    diff_df.to_csv(args.out_dir / "pass_diff.csv", index=False)

    cost_p1 = float(df1["rerun_cost_usd"].sum()) if "rerun_cost_usd" in df1.columns else 0.0
    cost_p2 = float(df2["rerun_cost_usd"].sum()) if "rerun_cost_usd" in df2.columns else 0.0

    pass1_ts = (
        df1["rerun_checked_at"].dropna().astype(str).iloc[0]
        if "rerun_checked_at" in df1.columns and not df1["rerun_checked_at"].dropna().empty
        else "unknown"
    )
    pass2_ts = (
        df2["rerun_checked_at"].dropna().astype(str).iloc[0]
        if "rerun_checked_at" in df2.columns and not df2["rerun_checked_at"].dropna().empty
        else "unknown"
    )

    report = _format_report(
        diffs=diffs,
        classification=classification,
        median_jaccard=median_jaccard,
        counts=counts,
        cost_pass1=cost_p1,
        cost_pass2=cost_p2,
        pass1_ts=pass1_ts,
        pass2_ts=pass2_ts,
    )
    report_path = args.out_dir / "iter14_phase0_retrieval_stability.md"
    report_path.write_text(report, encoding="utf-8")

    logger.info("=" * 60)
    logger.info("Phase 0 complete.")
    logger.info("  Rows compared:   %d", len(diffs))
    logger.info("  Median Jaccard:  %.3f", median_jaccard)
    logger.info("  Buckets:         %s", dict(counts))
    logger.info("  Classification:  %s", classification)
    logger.info("  Total cost:      $%.4f", cost_p1 + cost_p2)
    logger.info("  Report:          %s", report_path)


if __name__ == "__main__":
    main(sys.argv[1:])
