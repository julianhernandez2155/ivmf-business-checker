# Phase 5 — Full BMOSG Run (709 records)

**Date:** 2026-04-30 (run completed) / 2026-05-01 (snapshotted + sampled)
**Outcome:** ✅ Complete
**Tag:** `phase-5-bmosg-run`

## What was done

Ran `python3 run_checker.py --input ../data/BMOSG_All_Businesses.xlsx --workers 3` against the full 709-row BMOSG dataset.

### Results

| Metric | Value |
|---|---|
| Rows processed | 709 / 709 |
| Wall time | ~15 min (16:19 → 16:34, 2026-04-30) |
| Total cost | $5.0481 ($0.0071 avg / check) |
| Errors | 0 |
| Tracebacks | 0 |
| Cache hits | 20 (rows 1–20 from prior smoke runs — free) |

### Status distribution

| Status | Count | % |
|---|---|---|
| Active | 608 | 85.8% |
| Uncertain | 63 | 8.9% |
| Likely Closed | 38 | 5.4% |
| No Web Presence | 0 | 0.0% |

The 0% No Web Presence finding is meaningful — every BMOSG business has at least some online footprint, which is consistent with a curated IVMF dataset where entries were vetted at registration. **For Phase 6 eval, the 80-row plan (n=20 per status) becomes a 60-row eval (n=20 from the 3 populated statuses).** Documented as a v1 limitation in the leadership packet.

## Artifacts produced

All under `business_checker/Runs/BMOSG_All_Businesses_2026-04-30_1619/`:

| File | Size | Purpose |
|---|---|---|
| `checkpoint.csv` | 391 KB | Per-row predictions (709 rows + header) |
| `BMOSG_All_Businesses_Results.xlsx` | 323 KB | Color-coded Excel with AI columns left, original right |
| `run.log` | 101 KB | Full stdout/stderr audit trail |

**Predictions snapshot copied to:**
- `business_checker/eval/datasets/bmosg_v1_predictions_2026-04-30.csv`

**Checksums (for reproducibility):**
- Input: `../data/BMOSG_All_Businesses.xlsx` md5 `0c27145f3a5ba463a12b1fd5ab8d15e7`
- Predictions snapshot: md5 `7617e9477bad9f0ecdec1b3b4c8c2cbc`

## Eval sample generated

```bash
python3 -m eval.sample \
  --checkpoint eval/datasets/bmosg_v1_predictions_2026-04-30.csv \
  --input-xlsx ../data/BMOSG_All_Businesses.xlsx \
  --n-per-status 20 --seed 42 \
  --out eval/datasets/bmosg_v1_eval_sample.csv
```

Output: `business_checker/eval/datasets/bmosg_v1_eval_sample.csv` — 60 rows (20 Active + 20 Likely Closed + 20 Uncertain), city/state populated, ready for Phase 6 labeling.

Confidence distribution across the sample:
- min=50, max=100, mean=78.2, median=75
- 49 unique cities, 22 unique states represented (good geographic spread)

## Risks encountered

1. **Background process invisibility:** the run was launched in the background and a monitor was attached, but Julian's laptop slept while the run was active. The monitor died with the wake-resume cycle. Run itself was unaffected — finished at 16:34, 15 min later, with zero errors. Lesson logged: for long unattended runs, prefer `nohup` (already used) + a completion-marker file pattern instead of an in-conversation monitor.

2. **No Web Presence is empty (sample bucket missing):** see above.

## Verification

- 709 rows in checkpoint ✓
- Per-status distribution sane (not all one bucket) ✓
- Total cost within 2× estimate ($5.05 vs $5–10 expected) ✓
- 0 errors ✓
- Eval sample produced 60 rows with city/state populated ✓
- Run snapshotted to eval/datasets/ with checksum logged ✓

## Files of note

- `business_checker/eval/datasets/bmosg_v1_predictions_2026-04-30.csv` — frozen predictions
- `business_checker/eval/datasets/bmosg_v1_eval_sample.csv` — labeling target

## Next phase

Phase 6 — Julian labels the 60-row sample via Streamlit:

```bash
cd business_checker
streamlit run eval/review_app.py -- --dataset eval/datasets/bmosg_v1_eval_sample.csv
```

Estimated time: 5–6 hours (60 rows × ~5 min per row, split across 2+ sessions). The labeled CSV at `eval/datasets/bmosg_v1_eval_sample.csv` is overwritten in place after each Save & Next.
