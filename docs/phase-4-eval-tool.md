# Phase 4 — Build Eval Harness + Codex Review #2

**Date:** 2026-04-30
**Outcome:** ✅ Complete
**Tag:** `phase-4-eval-tool`

## What was built

`business_checker/eval/` package — 8 new files, 1,250 lines, 21 new pytest tests:

| File | Lines | Purpose |
|---|---|---|
| `eval/sample.py` | 217 | Stratified sampler. CLI: `python -m eval.sample --checkpoint X --input-xlsx Y --n-per-status 20 --seed 42 --out Z` |
| `eval/score.py` | 360 | Metrics: agreement + Wilson 95% CI, per-status P/R/F1 (4 labels always), confusion matrix, calibration curve, off-ontology validation, markdown report |
| `eval/review_app.py` | 280 | Streamlit labeling UI; quick links use name + city + state; idempotent CSV writes |
| `eval/LABELING_PROTOCOL.md` | 220 | Production labeling rules + addendum for marketplace-native / food-truck / mobile / e-commerce-only businesses |
| `eval/tests/test_sample.py` | 170 | 9 tests: stratification, empty buckets, undersized buckets, seed reproducibility, evidence/citations split |
| `eval/tests/test_score.py` | 256 | 12 tests: perfect/zero/partial agreement, UTD exclusion, confusion matrix shape, calibration buckets, report file generation |

## Codex review process

**Attempt 1 (failed):** Initial Codex CLI invocation hung after ~40 minutes. The sandbox kept blocking subprocess calls Codex tried to use for verification (e.g., running snippets of `from sklearn.metrics import classification_report; ...`). Killed at 15:56. Output preserved at `/tmp/codex-review-2.txt` for forensics.

**Self-review (interim):** While Codex was stuck, I reviewed my own subagent's eval code. Found one P0 bug (city/state never carried into the labeled CSV — would have made labeling much harder) and shipped the fix. Documented findings in `docs/codex-review-2-eval.md`.

**Attempt 2 (succeeded):** Re-issued Codex with an explicit "static review only — do not run scripts" directive. ~5 min wall time, 30k tokens. Codex confirmed most of the self-review and added 4 real findings I missed.

## Codex's findings (and how I handled them)

| # | Finding | Action |
|---|---|---|
| 1 | Headline metric should add macro-F1 alongside agreement | Deferred to Phase 7 (when real data is in) |
| 2 | Punting on confidence double-stratification at n=80 is correct | Confirmed |
| 3 | Wilson CI hand-rolled math is correct | Confirmed |
| 4 | classification_report should use ALL 4 labels, not present_labels | **Applied** — `score.py` now passes all 4 STATUS_LABELS with zero_division=0 |
| 5 | LABELING_PROTOCOL has gaps for single-channel businesses | **Applied** — added addendum covering marketplace-native, food-truck, mobile/home-based, e-commerce-only |
| 6a | quick_links search by name only (common-name routing failure) | **Applied** — Google/Maps/Facebook/LinkedIn now use name + city + state |
| 6b | No off-ontology validation in score.py | **Applied** — score.py now raises ValueError with clear message if predicted/human values aren't in the canonical 4 + UTD set |

## End-to-end verification

```bash
cd business_checker

# Sample the smoke checkpoint with location enrichment
python3 -m eval.sample \
  --checkpoint Runs/BMOSG_All_Businesses_2026-04-30_1502/checkpoint.csv \
  --input-xlsx ../data/BMOSG_All_Businesses.xlsx \
  --n-per-status 5 --seed 42 --out /tmp/test_with_loc.csv

# Output shape:
# 6 rows out (5 Active + 1 Likely Closed; warning logged for undersized bucket)
# 13 columns including row_index, name, website, city, state, predicted_*,
#   human_label, human_justification, reviewed_at
# Sample rows confirm city/state populated correctly:
#   row 2 Agoge Life Inc., Chandler, Arizona
#   row 18 Deep Sea Salt Company, Orlando, Florida
```

```bash
# Score a hand-built fixture
python3 -m eval.score --labeled <fixture> --out-dir <out>
# → "Overall agreement: 90.0%, 95% Wilson CI: 59.6%–98.2%"
# → markdown report + confusion_matrix.csv generated correctly
```

## What was deferred (with justification)

**To Phase 7 (when scoring real labeled data):**
- macro-F1 + balanced accuracy in headline metric — apply once we know if the AI is biased toward one class
- Bootstrap CI on per-status P/R/F1 — at n=20 per status, intervals will be ±20pp; honest to report
- Single-number ECE (Expected Calibration Error) — the calibration table is already there; ECE is one summary line

**To post-demo:**
- Cohen's kappa for inter-rater reliability — requires a second labeler; v1 is documented as single-labeler
- Confidence × status double stratification — too small at n=80; revisit at n=160

**Rejected:**
- MCC as headline — too opaque for non-technical leadership
- Keyboard shortcuts in Streamlit — add only if the first 80-row session reveals it's needed

## Verification

- `cd business_checker && python3 -m pytest -q` → **111 passed** (90 existing + 21 new) ✓
- `python3 -m eval.sample` produces enriched sample with city/state ✓
- `python3 -m eval.score` produces correct metrics + markdown report ✓
- `streamlit run eval/review_app.py` opens, displays row, saves label ✓
- Codex review #2 captured at `docs/codex-review-2-eval.md` ✓
- All 4 actionable findings applied this phase ✓

## Files of note

- `docs/codex-review-2-eval.md` — full review (self + Codex) with triage table
- `business_checker/eval/score.py` — metrics + report writer
- `business_checker/eval/sample.py` — stratified sampler with optional location join
- `business_checker/eval/review_app.py` — Streamlit labeling UI
- `business_checker/eval/LABELING_PROTOCOL.md` — labeling rules + addendum

## Commits

```
b3f0be6 feat(eval): build evaluation harness — sample, score, review app
8ee2db9 fix(eval): join city/state from input xlsx into sample for labeler
9554f39 fix(eval): apply Codex review #2 — 4 corrections, 1 protocol expansion
```

`phase-4-eval-tool` tag points at 9554f39.
