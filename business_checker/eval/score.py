"""Eval scoring module for Business Checker labeled datasets.

Reads a labeled CSV (output of review_app.py or manual labeling), computes
agreement metrics, generates a markdown report, and writes a confusion matrix
CSV.

Usage (CLI):
    python -m eval.score \\
        --labeled eval/datasets/bmosg_v1_eval_labeled.csv \\
        --out-dir eval/reports/bmosg_v1/
"""

from __future__ import annotations

import argparse
import logging
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix

logger = logging.getLogger(__name__)

# Official status labels in a stable display order.
STATUS_LABELS: list[str] = ["Active", "Likely Closed", "Uncertain", "No Web Presence"]

# Human label value that signals the reviewer could not decide.
UNABLE_TO_DETERMINE: str = "Unable to Determine"

# Confidence bucket boundaries: [(label, low, high), ...]
CONFIDENCE_BUCKETS: list[tuple[str, int, int]] = [
    ("0–49", 0, 49),
    ("50–59", 50, 59),
    ("60–69", 60, 69),
    ("70–79", 70, 79),
    ("80–89", 80, 89),
    ("90–100", 90, 100),
]


# ---------------------------------------------------------------------------
# Wilson confidence interval (hand-rolled so we don't hard-depend on statsmodels)
# ---------------------------------------------------------------------------

def _wilson_ci(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """Compute Wilson score 95% confidence interval.

    Args:
        successes: Number of successes (agreements).
        total: Total observations.
        z: Z-score for desired confidence level (1.96 → 95%).

    Returns:
        Tuple of (lower_bound, upper_bound) in [0, 1].
    """
    if total == 0:
        return (0.0, 0.0)
    p_hat = successes / total
    denominator = 1 + z**2 / total
    centre = (p_hat + z**2 / (2 * total)) / denominator
    half_width = z * math.sqrt(p_hat * (1 - p_hat) / total + z**2 / (4 * total**2)) / denominator
    return (max(0.0, centre - half_width), min(1.0, centre + half_width))


def _try_wilson_statsmodels(successes: int, total: int) -> tuple[float, float]:
    """Attempt Wilson CI via statsmodels; fall back to hand-computed version.

    Args:
        successes: Number of agreements.
        total: Total labeled rows used.

    Returns:
        Tuple of (ci_low, ci_high) in [0, 1].
    """
    try:
        from statsmodels.stats.proportion import proportion_confint  # type: ignore[import]

        low, high = proportion_confint(successes, total, alpha=0.05, method="wilson")
        return (float(low), float(high))
    except Exception:
        return _wilson_ci(successes, total)


# ---------------------------------------------------------------------------
# Markdown helpers
# ---------------------------------------------------------------------------

def _md_table(headers: list[str], rows: list[list[Any]]) -> str:
    """Render a list of rows as a markdown table string.

    Args:
        headers: Column header labels.
        rows: Each inner list is one row; values are stringified.

    Returns:
        Multi-line markdown table string (no trailing newline).
    """
    def fmt(val: Any) -> str:
        return str(val) if val is not None else ""

    header_line = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"
    body_lines = ["| " + " | ".join(fmt(v) for v in row) + " |" for row in rows]
    return "\n".join([header_line, separator] + body_lines)


# ---------------------------------------------------------------------------
# Core scoring logic
# ---------------------------------------------------------------------------

def score(
    labeled_csv: Path | str,
    out_dir: Path | str | None = None,
) -> dict:
    """Compute eval metrics and write a markdown report.

    Args:
        labeled_csv: Path to a labeled sample CSV.  Required columns:
            predicted_status, predicted_confidence (int or str coercible to int),
            human_label.
        out_dir: Directory to write report.md and confusion_matrix.csv.
            Defaults to eval/reports/.

    Returns:
        dict with keys: overall_agreement, agreement_ci_low, agreement_ci_high,
        per_status (dict), confusion_matrix (list[list[int]]),
        calibration (list[dict]).
    """
    labeled_csv = Path(labeled_csv)
    if not labeled_csv.exists():
        raise FileNotFoundError(f"Labeled CSV not found: {labeled_csv}")

    out_dir = Path(out_dir) if out_dir is not None else Path("eval/reports")
    out_dir.mkdir(parents=True, exist_ok=True)

    df_raw = pd.read_csv(labeled_csv, dtype={"predicted_confidence": str})
    df_raw["predicted_confidence"] = df_raw["predicted_confidence"].astype(int)

    total_rows = len(df_raw)

    # Drop rows with no human label or with "Unable to Determine".
    unlabeled_mask = df_raw["human_label"].isna() | (df_raw["human_label"].str.strip() == "")
    unable_mask = df_raw["human_label"].str.strip() == UNABLE_TO_DETERMINE
    excluded_mask = unlabeled_mask | unable_mask
    excluded_count = int(excluded_mask.sum())

    df = df_raw[~excluded_mask].copy()
    n_labeled = len(df)

    if n_labeled == 0:
        raise ValueError("No labeled rows after excluding empty / Unable-to-Determine rows.")

    # -----------------------------------------------------------------------
    # Overall agreement
    # -----------------------------------------------------------------------
    agreements = int((df["predicted_status"] == df["human_label"]).sum())
    overall_agreement = agreements / n_labeled
    ci_low, ci_high = _try_wilson_statsmodels(agreements, n_labeled)

    # -----------------------------------------------------------------------
    # Per-status metrics via sklearn classification_report
    # -----------------------------------------------------------------------
    present_labels = [lbl for lbl in STATUS_LABELS if lbl in df["predicted_status"].values or lbl in df["human_label"].values]
    report_dict = classification_report(
        y_true=df["human_label"],
        y_pred=df["predicted_status"],
        labels=present_labels,
        zero_division=0,
        output_dict=True,
    )

    per_status: dict[str, dict[str, float]] = {
        lbl: {
            "n": int(report_dict.get(lbl, {}).get("support", 0)),
            "precision": round(float(report_dict.get(lbl, {}).get("precision", 0.0)), 3),
            "recall": round(float(report_dict.get(lbl, {}).get("recall", 0.0)), 3),
            "f1": round(float(report_dict.get(lbl, {}).get("f1-score", 0.0)), 3),
        }
        for lbl in present_labels
    }

    # -----------------------------------------------------------------------
    # Confusion matrix (always 4x4, ordered by STATUS_LABELS)
    # -----------------------------------------------------------------------
    cm = confusion_matrix(
        y_true=df["human_label"],
        y_pred=df["predicted_status"],
        labels=STATUS_LABELS,
    )
    cm_list: list[list[int]] = cm.tolist()

    pd.DataFrame(cm_list, index=STATUS_LABELS, columns=STATUS_LABELS).to_csv(
        out_dir / "confusion_matrix.csv"
    )

    # -----------------------------------------------------------------------
    # Calibration curve
    # -----------------------------------------------------------------------
    calibration: list[dict] = []
    for bucket_label, low, high in CONFIDENCE_BUCKETS:
        mask = (df["predicted_confidence"] >= low) & (df["predicted_confidence"] <= high)
        bucket_df = df[mask]
        n_bucket = len(bucket_df)
        if n_bucket == 0:
            calibration.append({"bucket": bucket_label, "n": 0, "agreement_rate": None})
            continue
        bucket_agreements = int((bucket_df["predicted_status"] == bucket_df["human_label"]).sum())
        calibration.append(
            {
                "bucket": bucket_label,
                "n": n_bucket,
                "agreement_rate": round(bucket_agreements / n_bucket, 3),
            }
        )

    # -----------------------------------------------------------------------
    # Disagreement summary
    # -----------------------------------------------------------------------
    disagreements = df[df["predicted_status"] != df["human_label"]]
    disagree_counts = (
        disagreements.groupby(["predicted_status", "human_label"])
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )

    # -----------------------------------------------------------------------
    # Build markdown report
    # -----------------------------------------------------------------------
    dataset_name = labeled_csv.stem
    now_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    per_status_rows = [
        [
            status,
            per_status[status]["n"],
            f"{per_status[status]['precision']:.1%}",
            f"{per_status[status]['recall']:.1%}",
            f"{per_status[status]['f1']:.3f}",
        ]
        for status in present_labels
    ]

    cm_headers = ["Predicted \\ Human"] + STATUS_LABELS
    cm_rows = [[STATUS_LABELS[i]] + row for i, row in enumerate(cm_list)]

    cal_rows = [
        [
            c["bucket"],
            c["n"],
            f"{c['agreement_rate']:.1%}" if c["agreement_rate"] is not None else "—",
        ]
        for c in calibration
    ]

    if disagree_counts.empty:
        disagree_section = "_No disagreements found — perfect agreement!_"
    else:
        disagree_section = _md_table(
            ["Predicted", "Human Label", "Count"],
            disagree_counts.values.tolist(),
        )

    report_md = f"""# Eval Report — {dataset_name}

**Generated:** {now_str}
**Source:** {labeled_csv}
**Total labeled rows:** {total_rows}
**Excluded (Unable to Determine or empty):** {excluded_count}

## Headline

**Overall agreement: {overall_agreement:.1%} (95% Wilson CI: {ci_low:.1%}–{ci_high:.1%}, n={n_labeled})**

## Per-status metrics

{_md_table(["Status", "n", "Precision", "Recall", "F1"], per_status_rows)}

## Confusion matrix

Rows = human label (true), columns = predicted label (AI).

{_md_table(cm_headers, cm_rows)}

## Calibration

{_md_table(["Confidence bucket", "n", "Agreement rate"], cal_rows)}

## Disagreement summary

{disagree_section}
"""

    report_path = out_dir / "report.md"
    report_path.write_text(report_md, encoding="utf-8")
    logger.info("Report written to %s", report_path)

    return {
        "overall_agreement": overall_agreement,
        "agreement_ci_low": ci_low,
        "agreement_ci_high": ci_high,
        "per_status": per_status,
        "confusion_matrix": cm_list,
        "calibration": calibration,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser for eval.score."""
    parser = argparse.ArgumentParser(
        prog="python -m eval.score",
        description="Score a labeled Business Checker eval dataset.",
    )
    parser.add_argument("--labeled", required=True, type=Path, help="Path to labeled CSV.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Directory for report.md + confusion_matrix.csv (default: eval/reports/).",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = _build_parser().parse_args(argv)
    result = score(labeled_csv=args.labeled, out_dir=args.out_dir)
    print(f"Overall agreement: {result['overall_agreement']:.1%}")
    print(f"95% Wilson CI: {result['agreement_ci_low']:.1%} – {result['agreement_ci_high']:.1%}")


if __name__ == "__main__":
    main(sys.argv[1:])
