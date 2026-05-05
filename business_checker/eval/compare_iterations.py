"""Compare two iterations of an eval sample (baseline vs. iteration N).

Loads the labeled sample (with human ground truth) and the iteration N
predictions, and produces:
  - per-row before/after comparison
  - aggregate stats: agreement delta, resolutions, regressions
  - per-status confusion matrix shifts
  - calibration shifts
  - markdown report

Usage:
    python -m eval.compare_iterations \\
        --baseline eval/datasets/bmosg_v1_eval_sample.csv \\
        --iteration eval/datasets/bmosg_v1_iteration_1_predictions.csv \\
        --out-dir eval/reports/iteration_1_comparison
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

STATUS_LABELS = ["Active", "Likely Closed", "Uncertain", "No Web Presence"]
UNABLE_TO_DETERMINE = "Unable to Determine"


def _load(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"predicted_confidence": str})
    df["predicted_confidence"] = df["predicted_confidence"].astype(int)
    df["row_index"] = df["row_index"].astype(int)
    return df.set_index("row_index", drop=False)


def _classify(baseline_match: bool, new_match: bool) -> str:
    if baseline_match and new_match:
        return "unchanged_correct"
    if not baseline_match and not new_match:
        return "unchanged_wrong"
    if not baseline_match and new_match:
        return "resolved"
    return "regressed"


def compare(baseline_csv: Path, iteration_csv: Path, out_dir: Path) -> dict:
    base = _load(baseline_csv)
    new = _load(iteration_csv)

    out_dir.mkdir(parents=True, exist_ok=True)

    common_idx = base.index.intersection(new.index)
    if len(common_idx) != len(base):
        logger.warning("Iteration covers %d / %d baseline rows", len(common_idx), len(base))
    base = base.loc[common_idx].copy()
    new = new.loc[common_idx].copy()

    # Drop UTD and empty-human-label rows for scoring; keep them for the
    # detailed per-row table for transparency.
    is_utd = base["human_label"].astype(str).str.strip() == UNABLE_TO_DETERMINE
    has_label = base["human_label"].astype(str).str.strip() != ""
    scoreable = has_label & ~is_utd

    base["base_match"] = base["predicted_status"] == base["human_label"]
    new["new_match"] = new["predicted_status"] == base["human_label"]

    classification = []
    for idx in common_idx:
        bm = bool(base.at[idx, "base_match"])
        nm = bool(new.at[idx, "new_match"])
        classification.append(_classify(bm, nm))
    base["change_class"] = classification

    # Per-row table
    per_row = pd.DataFrame({
        "row_index": base.index,
        "name": base["name"],
        "human_label": base["human_label"],
        "baseline_status": base["predicted_status"],
        "baseline_conf": base["predicted_confidence"],
        "iteration_status": new["predicted_status"],
        "iteration_conf": new["predicted_confidence"],
        "change_class": base["change_class"],
        "scoreable": scoreable,
    }).reset_index(drop=True)
    per_row.to_csv(out_dir / "per_row_comparison.csv", index=False)

    # Aggregate metrics
    sb = base[scoreable]
    sn = new[scoreable]

    base_agree = int(sb["base_match"].sum())
    new_agree = int(sn["new_match"].sum())
    n = len(sb)

    base_pct = base_agree / n if n else 0
    new_pct = new_agree / n if n else 0

    resolved = int(((~sb["base_match"]) & (sn["new_match"])).sum())
    regressed = int(((sb["base_match"]) & (~sn["new_match"])).sum())
    unchanged_correct = int(((sb["base_match"]) & (sn["new_match"])).sum())
    unchanged_wrong = int(((~sb["base_match"]) & (~sn["new_match"])).sum())

    # Confusion matrices
    def cm(df_sub: pd.DataFrame, pred_col: str) -> pd.DataFrame:
        return (
            pd.crosstab(
                df_sub["human_label"],
                df_sub[pred_col],
                rownames=["truth"],
                colnames=["predicted"],
                dropna=False,
            )
            .reindex(index=STATUS_LABELS, columns=STATUS_LABELS, fill_value=0)
        )

    base_cm = cm(sb, "predicted_status")
    new_cm = cm(sn, "predicted_status")

    base_cm.to_csv(out_dir / "baseline_confusion.csv")
    new_cm.to_csv(out_dir / "iteration_confusion.csv")

    # Calibration shift
    buckets = [(50, 59), (60, 69), (70, 79), (80, 89), (90, 100)]
    cal_rows = []
    for lo, hi in buckets:
        bmask = (sb["predicted_confidence"] >= lo) & (sb["predicted_confidence"] <= hi)
        nmask = (sn["predicted_confidence"] >= lo) & (sn["predicted_confidence"] <= hi)
        b_count = int(bmask.sum())
        n_count = int(nmask.sum())
        b_acc = float(sb[bmask]["base_match"].mean()) if b_count else None
        n_acc = float(sn[nmask]["new_match"].mean()) if n_count else None
        cal_rows.append({
            "bucket": f"{lo}-{hi}",
            "baseline_n": b_count,
            "baseline_accuracy": b_acc,
            "iteration_n": n_count,
            "iteration_accuracy": n_acc,
        })

    # Disagreement rows analysis (for detailed report)
    disagreements_now = sn[~sn["new_match"]].copy()
    disagreements_now["baseline_status"] = sb["predicted_status"]
    disagreements_now["change_class"] = sb["change_class"]

    # Build markdown report
    md = []
    md.append(f"# Iteration 1 vs Baseline Comparison\n")
    md.append(f"**Baseline:** `{baseline_csv}`")
    md.append(f"**Iteration:** `{iteration_csv}`")
    md.append(f"**Scoreable rows (excludes UTD/empty):** {n}\n")
    md.append("## Headline\n")
    md.append(f"| Metric | Baseline | Iteration 1 | Delta |")
    md.append(f"|---|---|---|---|")
    md.append(f"| Agreement | {base_agree}/{n} = {base_pct:.1%} | {new_agree}/{n} = {new_pct:.1%} | "
              f"**{(new_pct - base_pct)*100:+.1f} pp** |")
    md.append(f"\n## Change classification\n")
    md.append(f"| Class | Count | Description |")
    md.append(f"|---|---|---|")
    md.append(f"| Resolved | {resolved} | Was wrong before, now correct |")
    md.append(f"| Regressed | {regressed} | Was correct before, now wrong |")
    md.append(f"| Unchanged (correct) | {unchanged_correct} | Correct in both |")
    md.append(f"| Unchanged (wrong) | {unchanged_wrong} | Wrong in both |")
    md.append(f"| **Net delta** | **{resolved - regressed:+d}** | resolved − regressed |")

    md.append(f"\n## Baseline confusion matrix (rows = your label, cols = AI)\n")
    md.append(base_cm.to_markdown())
    md.append(f"\n## Iteration confusion matrix (rows = your label, cols = AI)\n")
    md.append(new_cm.to_markdown())

    md.append(f"\n## Calibration: confidence band vs accuracy\n")
    md.append("| Band | Baseline n | Baseline acc | Iteration n | Iteration acc |")
    md.append("|---|---|---|---|---|")
    for r in cal_rows:
        b_acc = f"{r['baseline_accuracy']:.0%}" if r['baseline_accuracy'] is not None else "—"
        n_acc = f"{r['iteration_accuracy']:.0%}" if r['iteration_accuracy'] is not None else "—"
        md.append(f"| {r['bucket']} | {r['baseline_n']} | {b_acc} | {r['iteration_n']} | {n_acc} |")

    md.append(f"\n## Resolved rows (baseline wrong → iteration correct)\n")
    resolved_df = sb[(~sb["base_match"]) & (sn["new_match"])].copy()
    if resolved_df.empty:
        md.append("_None._")
    else:
        for idx in resolved_df.index:
            md.append(f"\n### Row {idx} — {sb.at[idx, 'name']}")
            md.append(f"- Your label: **{sb.at[idx, 'human_label']}**")
            md.append(f"- Baseline AI: **{sb.at[idx, 'predicted_status']}** "
                      f"({sb.at[idx, 'predicted_confidence']}%)")
            md.append(f"- Iteration AI: **{sn.at[idx, 'predicted_status']}** "
                      f"({sn.at[idx, 'predicted_confidence']}%) ✓")
            evidence = str(sn.at[idx, "predicted_evidence"])[:300]
            md.append(f"- Iteration evidence: _{evidence}_")

    md.append(f"\n## Regressed rows (baseline correct → iteration wrong)\n")
    regressed_df = sb[(sb["base_match"]) & (~sn["new_match"])].copy()
    if regressed_df.empty:
        md.append("_None — no regressions._")
    else:
        for idx in regressed_df.index:
            md.append(f"\n### Row {idx} — {sb.at[idx, 'name']}")
            md.append(f"- Your label: **{sb.at[idx, 'human_label']}**")
            md.append(f"- Baseline AI: **{sb.at[idx, 'predicted_status']}** "
                      f"({sb.at[idx, 'predicted_confidence']}%) ✓")
            md.append(f"- Iteration AI: **{sn.at[idx, 'predicted_status']}** "
                      f"({sn.at[idx, 'predicted_confidence']}%) ✗")
            evidence = str(sn.at[idx, "predicted_evidence"])[:300]
            md.append(f"- Iteration evidence: _{evidence}_")

    md.append(f"\n## Still-disagreement rows (wrong in both)\n")
    still_wrong = sb[(~sb["base_match"]) & (~sn["new_match"])].copy()
    if still_wrong.empty:
        md.append("_None._")
    else:
        for idx in still_wrong.index:
            md.append(f"\n### Row {idx} — {sb.at[idx, 'name']}")
            md.append(f"- Your label: **{sb.at[idx, 'human_label']}**")
            md.append(f"- Baseline AI: **{sb.at[idx, 'predicted_status']}** "
                      f"({sb.at[idx, 'predicted_confidence']}%)")
            md.append(f"- Iteration AI: **{sn.at[idx, 'predicted_status']}** "
                      f"({sn.at[idx, 'predicted_confidence']}%)")

    report_path = out_dir / "report.md"
    report_path.write_text("\n".join(md), encoding="utf-8")
    logger.info("Report written to %s", report_path)

    return {
        "baseline_agreement": base_pct,
        "iteration_agreement": new_pct,
        "delta_pp": (new_pct - base_pct) * 100,
        "resolved": resolved,
        "regressed": regressed,
        "unchanged_correct": unchanged_correct,
        "unchanged_wrong": unchanged_wrong,
        "n": n,
    }


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m eval.compare_iterations")
    p.add_argument("--baseline", required=True, type=Path)
    p.add_argument("--iteration", required=True, type=Path)
    p.add_argument("--out-dir", required=True, type=Path)
    return p


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = _build_parser().parse_args(argv)
    result = compare(args.baseline, args.iteration, args.out_dir)
    print(f"\nBaseline agreement:  {result['baseline_agreement']:.1%}")
    print(f"Iteration agreement: {result['iteration_agreement']:.1%}")
    print(f"Delta:               {result['delta_pp']:+.1f} pp")
    print(f"Resolved: {result['resolved']}, Regressed: {result['regressed']}")
    print(f"Net: {result['resolved'] - result['regressed']:+d}")


if __name__ == "__main__":
    main(sys.argv[1:])
