"""Eval scoring module for Business Checker labeled datasets.

Reads a labeled CSV (output of review_app.py or manual labeling), computes
agreement metrics, generates a markdown report, and writes a confusion matrix
CSV.

Usage (CLI):
    python -m eval.score \\
        --labeled eval/datasets/bmosg_v1_eval_labeled.csv \\
        --out-dir eval/reports/bmosg_v1/

Iter 13 extensions:
    Adds `decisive_accuracy`, `harmful_flips_total`,
    `harmful_flips_active_to_closed`, `harmful_flips_closed_to_active`,
    `review_queue_size`, and a `slices` dict broken down by reachability
    category. These are the metrics the production runner is being
    optimized against; surfacing them in the score-API removes the manual
    analysis step from every iteration.
"""

from __future__ import annotations

import argparse
import logging
import math
import re
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

def _normalize_name(value: Any) -> str:
    """Lowercase + strip punctuation + collapse whitespace, NaN-safe.

    Used to join the labeled CSV against `bmosg_v1_reachability_tags.csv`
    even when one side has `Fundraiser Blankets®` and the other has
    `Fundraiser Blankets`.
    """
    if value is None:
        return ""
    try:
        if value != value:  # NaN
            return ""
    except Exception:
        pass
    text = str(value).strip().lower()
    if text == "nan":
        return ""
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _decisive_mask(predicted: pd.Series) -> pd.Series:
    """Boolean mask: rows where the system committed to a non-Uncertain verdict.

    Per `docs/EVAL_BASELINES.md` definition: decisive means Active, Likely
    Closed, OR No Web Presence. Only `Uncertain` is excluded — both from
    the numerator and denominator of `decisive_accuracy`.
    """
    return predicted != "Uncertain"


def _count_harmful_flips(predicted: pd.Series, human: pd.Series) -> tuple[int, int]:
    """Return (active_to_closed, closed_to_active) harmful-flip counts.

    `active_to_closed`: predicted=Active, human=Likely Closed
        (false positive on Active — would trigger wasted outreach)
    `closed_to_active`: predicted=Likely Closed, human=Active
        (false negative on Active — would skip a real customer)

    Tracked separately so a regression in one direction can't hide behind
    an improvement in the other.
    """
    a_to_c = int(((predicted == "Active") & (human == "Likely Closed")).sum())
    c_to_a = int(((predicted == "Likely Closed") & (human == "Active")).sum())
    return a_to_c, c_to_a


def _compute_canonical_metrics(df: pd.DataFrame) -> dict[str, Any]:
    """Compute the iter-13 extended metrics on a labeled DataFrame.

    Pre-condition: `df` has been filtered to labeled rows only
    (no NaN/empty/Unable-to-Determine human labels).
    """
    n = len(df)
    if n == 0:
        return {
            "n": 0,
            "decisive_accuracy": None,
            "decisive_n": 0,
            "harmful_flips_total": 0,
            "harmful_flips_active_to_closed": 0,
            "harmful_flips_closed_to_active": 0,
        }

    predicted = df["predicted_status"]
    human = df["human_label"]

    decisive_mask = _decisive_mask(predicted)
    decisive_n = int(decisive_mask.sum())
    if decisive_n > 0:
        agreements = int(
            (predicted[decisive_mask] == human[decisive_mask]).sum()
        )
        decisive_accuracy = agreements / decisive_n
    else:
        decisive_accuracy = None

    a_to_c, c_to_a = _count_harmful_flips(predicted, human)

    return {
        "n": int(n),
        "decisive_accuracy": decisive_accuracy,
        "decisive_n": decisive_n,
        "harmful_flips_total": a_to_c + c_to_a,
        "harmful_flips_active_to_closed": a_to_c,
        "harmful_flips_closed_to_active": c_to_a,
    }


def _build_slices(
    df: pd.DataFrame,
    tags_path: Path | None,
) -> dict[str, dict[str, Any]]:
    """Compute per-reachability-bucket metrics by joining on normalized name.

    Returns a dict keyed by reachability bucket. Rows without a reachability
    tag are placed in `untagged` and a warning is logged. The reachability
    tag CSV is optional — if missing, only an `all` slice is returned.
    """
    slices: dict[str, dict[str, Any]] = {"all": _compute_canonical_metrics(df)}

    if tags_path is None or not Path(tags_path).exists():
        if tags_path is not None:
            logger.warning(
                "Reachability tags file not found: %s — skipping slice metrics",
                tags_path,
            )
        return slices

    tags_df = pd.read_csv(tags_path)
    tags_df["_join_key"] = tags_df["name"].apply(_normalize_name)
    df = df.copy()
    df["_join_key"] = df["name"].apply(_normalize_name)

    merged = df.merge(
        tags_df[["_join_key", "reachability"]], on="_join_key", how="left"
    )

    untagged = merged["reachability"].isna().sum()
    if untagged:
        logger.warning(
            "%d rows have no reachability tag — placed in 'untagged' bucket", untagged
        )
        merged.loc[merged["reachability"].isna(), "reachability"] = "untagged"

    for bucket in sorted(merged["reachability"].unique()):
        bucket_df = merged[merged["reachability"] == bucket]
        slices[bucket] = _compute_canonical_metrics(bucket_df)

    return slices


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
    reachability_tags: Path | str | None = None,
) -> dict:
    """Compute eval metrics and write a markdown report.

    Args:
        labeled_csv: Path to a labeled sample CSV. Required columns:
            predicted_status, predicted_confidence (int or str coercible to int),
            human_label. Optional column: `requires_review` for queue-size
            metric.
        out_dir: Directory to write report.md and confusion_matrix.csv.
            Defaults to eval/reports/.
        reachability_tags: Optional path to a reachability-tag CSV with
            `name` + `reachability` columns. When provided, the result
            dict's `slices` key is populated with per-bucket metrics.
            Defaults to `eval/datasets/bmosg_v1_reachability_tags.csv`
            relative to CWD when present.

    Returns:
        Dict with keys:
            overall_agreement, agreement_ci_low, agreement_ci_high,
            per_status, confusion_matrix, calibration (legacy),
            decisive_accuracy, decisive_n, harmful_flips_total,
            harmful_flips_active_to_closed, harmful_flips_closed_to_active,
            review_queue_size, slices (iter 13 extensions).
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

    # Defensive validation — the AI is constrained by Pydantic to emit only
    # the 4 canonical statuses, but this catches data corruption (manual CSV
    # edits, future model swaps that bypass the schema) before it silently
    # skews the metrics.
    valid_pred = set(STATUS_LABELS)
    valid_human = valid_pred | {UNABLE_TO_DETERMINE}
    bad_pred = set(df["predicted_status"]) - valid_pred
    bad_human = set(df["human_label"]) - valid_human
    if bad_pred:
        raise ValueError(
            f"predicted_status contains off-ontology values: {sorted(bad_pred)}. "
            f"Expected one of {STATUS_LABELS}."
        )
    if bad_human:
        raise ValueError(
            f"human_label contains off-ontology values: {sorted(bad_human)}. "
            f"Expected one of {STATUS_LABELS + [UNABLE_TO_DETERMINE]} (or empty)."
        )

    # -----------------------------------------------------------------------
    # Overall agreement
    # -----------------------------------------------------------------------
    agreements = int((df["predicted_status"] == df["human_label"]).sum())
    overall_agreement = agreements / n_labeled
    ci_low, ci_high = _try_wilson_statsmodels(agreements, n_labeled)

    # -----------------------------------------------------------------------
    # Per-status metrics via sklearn classification_report
    #
    # Always pass ALL 4 canonical labels with zero_division=0, even if a
    # status didn't appear in this batch. Filtering to "present" labels
    # silently hides absent classes — exactly the case leadership needs to
    # see (e.g. "the AI never produced any 'No Web Presence' verdicts").
    # -----------------------------------------------------------------------
    report_dict = classification_report(
        y_true=df["human_label"],
        y_pred=df["predicted_status"],
        labels=STATUS_LABELS,
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
        for lbl in STATUS_LABELS
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
    # Iter-13 canonical metrics: decisive accuracy, harmful flips (both
    # directions), review-queue size, reachability slices. These are the
    # metrics every config change is judged against.
    # -----------------------------------------------------------------------
    canonical = _compute_canonical_metrics(df)

    if "requires_review" in df.columns:
        # Pandas casts bools-as-string to object; coerce safely.
        review_queue_size = int(
            df["requires_review"].astype(str).str.lower().isin(
                {"true", "1", "yes"}
            ).sum()
        )
    else:
        review_queue_size = 0

    if reachability_tags is None:
        # Best-effort default: look next to the labeled CSV first, then
        # the canonical project location relative to CWD.
        default_tag_paths = [
            labeled_csv.parent / "bmosg_v1_reachability_tags.csv",
            Path("eval/datasets/bmosg_v1_reachability_tags.csv"),
        ]
        for candidate in default_tag_paths:
            if candidate.exists():
                reachability_tags = candidate
                break
    slices = _build_slices(
        df, Path(reachability_tags) if reachability_tags else None
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
        for status in STATUS_LABELS
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

    # Iter-13 canonical metrics table for the report.
    dec_acc = canonical["decisive_accuracy"]
    canonical_md = _md_table(
        ["Metric", "Value"],
        [
            [
                "decisive_accuracy",
                f"{dec_acc:.1%} (n={canonical['decisive_n']})"
                if dec_acc is not None else f"— (n={canonical['decisive_n']})",
            ],
            ["harmful_flips_total", canonical["harmful_flips_total"]],
            [
                "harmful_flips_active_to_closed",
                canonical["harmful_flips_active_to_closed"],
            ],
            [
                "harmful_flips_closed_to_active",
                canonical["harmful_flips_closed_to_active"],
            ],
            ["review_queue_size", review_queue_size],
        ],
    )

    def _fmt_acc(metrics: dict) -> str:
        v = metrics.get("decisive_accuracy")
        return f"{v:.1%}" if v is not None else "—"

    slice_rows = []
    for bucket, metrics in slices.items():
        slice_rows.append([
            bucket,
            metrics["n"],
            _fmt_acc(metrics),
            metrics["harmful_flips_total"],
            metrics["harmful_flips_active_to_closed"],
            metrics["harmful_flips_closed_to_active"],
        ])
    slices_md = _md_table(
        ["Slice", "n", "Decisive acc.", "Harmful (total)", "A→C", "C→A"],
        slice_rows,
    )

    report_md = f"""# Eval Report — {dataset_name}

**Generated:** {now_str}
**Source:** {labeled_csv}
**Total labeled rows:** {total_rows}
**Excluded (Unable to Determine or empty):** {excluded_count}

## Headline

**Overall agreement: {overall_agreement:.1%} (95% Wilson CI: {ci_low:.1%}–{ci_high:.1%}, n={n_labeled})**

## Canonical metrics (iter 13)

{canonical_md}

## Slices (by reachability)

{slices_md}

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
        # Iter-13 canonical metrics (per docs/EVAL_BASELINES.md definitions).
        "decisive_accuracy": canonical["decisive_accuracy"],
        "decisive_n": canonical["decisive_n"],
        "harmful_flips_total": canonical["harmful_flips_total"],
        "harmful_flips_active_to_closed": canonical["harmful_flips_active_to_closed"],
        "harmful_flips_closed_to_active": canonical["harmful_flips_closed_to_active"],
        "review_queue_size": review_queue_size,
        "slices": slices,
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
    parser.add_argument(
        "--reachability-tags",
        type=Path,
        default=None,
        help="Optional path to a reachability-tag CSV. Defaults to the "
             "canonical project location when present.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = _build_parser().parse_args(argv)
    result = score(
        labeled_csv=args.labeled,
        out_dir=args.out_dir,
        reachability_tags=args.reachability_tags,
    )
    print(f"Overall agreement: {result['overall_agreement']:.1%}")
    print(f"95% Wilson CI: {result['agreement_ci_low']:.1%} – {result['agreement_ci_high']:.1%}")
    dec_acc = result.get("decisive_accuracy")
    if dec_acc is not None:
        print(f"Decisive accuracy: {dec_acc:.1%} (n={result['decisive_n']})")
    print(
        f"Harmful flips: total={result['harmful_flips_total']} "
        f"(A→C={result['harmful_flips_active_to_closed']}, "
        f"C→A={result['harmful_flips_closed_to_active']})"
    )
    print(f"Review queue size: {result['review_queue_size']}")


if __name__ == "__main__":
    main(sys.argv[1:])
