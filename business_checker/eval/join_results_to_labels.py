"""Join a fresh Results.xlsx run against an existing labeled CSV.

Produced for iter 13 Phase A gate A2: a fresh `run_checker.py --pipeline v11`
emits `Results.xlsx` (no human labels). To score it against the historical
iter 11 labels, we need to attach the human_label / human_justification
columns from the existing labeled CSV onto fresh predictions.

Joins on a normalized (name, city, state) tuple — the same normalization
used in `tools/cache.py` so two records that hash to the same cache key
also join here. Unmatched rows on either side are logged with counts and
skipped (never silently dropped).

Usage (CLI):
    python -m eval.join_results_to_labels \\
        --results Runs/<latest>/eval_60_Results.xlsx \\
        --labels  eval/datasets/bmosg_v1_iteration_11_fb.csv \\
        --out     eval/reports/v11_fresh/labeled.csv
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

import openpyxl
import pandas as pd

logger = logging.getLogger(__name__)


def _normalize(value: object) -> str:
    """Lowercase + strip punctuation + collapse whitespace.

    Must match `tools.cache._normalize_part` semantics so the join key
    behaves identically to the cache key.

    Treats `None`, NaN (via pandas), and the literal string "nan" as the
    empty string — pandas DataFrames returned from `read_csv` represent
    missing values as NaN, which `str(NaN)` turns into the literal
    "nan" and would otherwise produce phantom join keys.
    """
    if value is None:
        return ""
    # Catch pandas / numpy NaN without forcing a pandas import here.
    try:
        if value != value:  # NaN is not equal to itself
            return ""
    except Exception:
        pass
    text = str(value).strip().lower()
    if text == "nan":
        return ""
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _make_join_key(name: object, city: object, state: object) -> str:
    return f"{_normalize(name)}|{_normalize(city)}|{_normalize(state)}"


def _read_results_xlsx(path: Path) -> pd.DataFrame:
    """Load a Results.xlsx into a DataFrame using openpyxl read_only mode."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    if not rows:
        raise ValueError(f"Results xlsx is empty: {path}")
    headers = [str(h).strip() if h is not None else "" for h in rows[0]]
    data = rows[1:]
    df = pd.DataFrame(data, columns=headers)
    return df


def join_results_to_labels(
    results_path: Path,
    labels_path: Path,
    out_path: Path,
) -> dict:
    """Attach human labels from `labels_path` onto fresh predictions in
    `results_path`, write the joined CSV to `out_path`, and return counts.

    Args:
        results_path: Path to a Results.xlsx emitted by run_checker.py.
        labels_path: Path to an existing labeled CSV with human_label,
            human_justification, reviewed_at columns.
        out_path: Where to write the joined labeled CSV.

    Returns:
        Dict with `matched`, `unmatched_results`, `unmatched_labels`,
        `total_results`, `total_labels` integer counts.
    """
    results_df = _read_results_xlsx(results_path)
    labels_df = pd.read_csv(labels_path)

    # Normalize column names for results. The production build_output
    # script writes "AI_Status / AI_Confidence / AI_Evidence" — these are
    # the verdict columns and must be remapped to the canonical
    # "status / confidence / evidence" the rest of the helper expects.
    # The original input columns (name, website, city, state) are
    # already lowercase in the Excel.
    #
    # The source dataset has its OWN `status` column (business type),
    # which conflicts with the AI verdict — we drop it before remapping.
    if "AI_Status" in results_df.columns and "status" in results_df.columns:
        results_df = results_df.drop(columns=["status"])

    ai_rename = {
        "AI_Status": "status",
        "AI_Confidence": "confidence",
        "AI_Evidence": "evidence",
        "AI_Checked_At": "checked_at",
    }
    results_df = results_df.rename(
        columns={k: v for k, v in ai_rename.items() if k in results_df.columns}
    )

    rename = {}
    for col in results_df.columns:
        lc = col.strip().lower()
        if lc in {"name", "website", "city", "state"}:
            rename[col] = lc
    results_df = results_df.rename(columns=rename)

    required_results_cols = {"name", "city", "state", "status", "confidence"}
    missing_in_results = required_results_cols - set(results_df.columns)
    if missing_in_results:
        raise ValueError(
            f"Results xlsx is missing required columns: {sorted(missing_in_results)}. "
            f"Got columns: {list(results_df.columns)}"
        )

    required_labels_cols = {"name", "city", "state", "human_label"}
    missing_in_labels = required_labels_cols - set(labels_df.columns)
    if missing_in_labels:
        raise ValueError(
            f"Labels CSV is missing required columns: {sorted(missing_in_labels)}"
        )

    # Build the join key on both sides.
    results_df["_join_key"] = results_df.apply(
        lambda r: _make_join_key(r["name"], r["city"], r["state"]), axis=1
    )
    labels_df["_join_key"] = labels_df.apply(
        lambda r: _make_join_key(r["name"], r["city"], r["state"]), axis=1
    )

    # Drop duplicates on the labels side — multiple labelings of the same
    # business would explode the join. Keep the last entry, which is the
    # one a human most recently confirmed.
    label_dups = labels_df["_join_key"].duplicated().sum()
    if label_dups:
        logger.warning(
            "%d duplicate join keys in labels CSV — keeping last occurrence per key",
            label_dups,
        )
        labels_df = labels_df.drop_duplicates(subset="_join_key", keep="last")

    # Carry forward the columns we need from labels.
    keep_label_cols = ["_join_key", "human_label"]
    for optional in ("human_justification", "reviewed_at", "row_index"):
        if optional in labels_df.columns:
            keep_label_cols.append(optional)
    labels_slim = labels_df[keep_label_cols]

    merged = results_df.merge(labels_slim, on="_join_key", how="outer", indicator=True)
    matched = int((merged["_merge"] == "both").sum())
    unmatched_results = int((merged["_merge"] == "left_only").sum())
    unmatched_labels = int((merged["_merge"] == "right_only").sum())

    if unmatched_results:
        logger.warning(
            "%d rows in Results.xlsx had no matching label — skipped from output",
            unmatched_results,
        )
    if unmatched_labels:
        logger.warning(
            "%d label rows had no matching Results row — skipped from output",
            unmatched_labels,
        )

    joined = merged[merged["_merge"] == "both"].copy()
    joined = joined.drop(columns=["_join_key", "_merge"])

    # Emit a CSV that the existing score() will accept: it needs
    # predicted_status, predicted_confidence, human_label.
    out = pd.DataFrame()
    if "row_index" in joined.columns:
        out["row_index"] = joined["row_index"]
    out["name"] = joined["name"]
    if "website" in joined.columns:
        out["website"] = joined["website"]
    out["city"] = joined["city"]
    out["state"] = joined["state"]
    out["predicted_status"] = joined["status"]
    out["predicted_confidence"] = joined["confidence"]
    if "evidence" in joined.columns:
        out["predicted_evidence"] = joined["evidence"]
    out["human_label"] = joined["human_label"]
    if "human_justification" in joined.columns:
        out["human_justification"] = joined["human_justification"]
    if "reviewed_at" in joined.columns:
        out["reviewed_at"] = joined["reviewed_at"]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_path, index=False)

    return {
        "matched": matched,
        "unmatched_results": unmatched_results,
        "unmatched_labels": unmatched_labels,
        "total_results": int(len(results_df)),
        "total_labels": int(len(labels_df)),
    }


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m eval.join_results_to_labels",
        description="Attach human labels from a labeled CSV onto a fresh Results.xlsx.",
    )
    p.add_argument("--results", required=True, type=Path,
                   help="Path to a Results.xlsx produced by run_checker.py")
    p.add_argument("--labels", required=True, type=Path,
                   help="Path to an existing labeled CSV with human_label column")
    p.add_argument("--out", required=True, type=Path,
                   help="Output joined labeled CSV path")
    return p


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = _build_parser().parse_args(argv)
    counts = join_results_to_labels(args.results, args.labels, args.out)
    print(
        f"Joined {counts['matched']} rows "
        f"(results={counts['total_results']}, labels={counts['total_labels']}, "
        f"unmatched_results={counts['unmatched_results']}, "
        f"unmatched_labels={counts['unmatched_labels']}). "
        f"Output: {args.out}"
    )


if __name__ == "__main__":
    main(sys.argv[1:])
