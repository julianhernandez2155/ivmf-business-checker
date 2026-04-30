# Codex Review #2 — Eval Design (self-review)

**Date:** 2026-04-30
**Reviewer:** Self-review by orchestrator (Claude Opus 4.7)
**Reason:** Codex CLI run aborted after ~40 min. Its sandbox kept blocking the python verification subprocesses it tried to run, leaving it unable to actually test edge cases. Output captured up to the abort is at `/tmp/codex-review-2.txt` (preserved as evidence) but contains no completed analysis.

This review is by the orchestrator that built and tested the eval pipeline. Surface area:
- `business_checker/eval/sample.py` (202 lines)
- `business_checker/eval/score.py` (342 lines)
- `business_checker/eval/review_app.py` (280 lines)
- `business_checker/eval/LABELING_PROTOCOL.md` (176 lines)
- `business_checker/eval/tests/test_sample.py` (170 lines)
- `business_checker/eval/tests/test_score.py` (256 lines)
- 21 new pytest tests, all passing

Not the same as a true second opinion — flagged for transparency. Codex review #3 (final) before leadership handoff is still planned and will catch what this review misses.

---

## Findings ranked by priority

### P0 — Block before labeling

**1. `S` City/state missing from review_app.py display.**
`review_app.py:185-186` reads `row.get("city", "")` and `row.get("state", "")`, but `sample.py` never populates those columns (the input checkpoint CSV doesn't contain them — only `name, website`). For a labeler trying to disambiguate businesses with common names ("Acme LLC" exists in many cities), this is a real defect. **Fix in this phase.**

**Implementation:** Add `--input-xlsx` flag to `sample.py`. When provided, join each sampled row to the input spreadsheet on `row_index` to enrich with `city` and `state`. Output two new columns to the labeled CSV. Default behavior (no `--input-xlsx`): emit empty city/state with a warning.

### P1 — Should fix before final leadership packet

**2. `S` Headline metric is overall agreement, which is misleading on imbalanced data.**
BMOSG's likely 70%+ Active baseline means a "predict-everything-as-Active" strategy scores ~70% accuracy. Need macro-F1 or balanced accuracy as the primary metric, with overall agreement as a secondary number. score.py already computes per-status F1 — just need to surface a `macro_f1` summary in the headline section of `report.md` and add Wilson CI for it via bootstrap.

**Decision:** apply in Phase 7 when scoring real labeled data. Don't refactor speculatively.

**3. `S` No bootstrap CI on per-status precision/recall/F1.**
Currently only overall agreement has a CI. Bootstrap would give per-status uncertainty bounds. For 80-row eval, per-status n is 20, so CIs will be wide — that's the honest answer to give leadership.

**Decision:** add in Phase 7 if time permits, otherwise document as "n=20 per status; per-status CIs not reported because intervals would be ±20pp at this sample size."

**4. `S` Calibration ECE not computed as a single number.**
ECE (Expected Calibration Error) is the standard one-number summary of how far calibration buckets deviate from perfect. Easy to add: `sum(|bucket_agreement - bucket_midpoint| * bucket_weight)`.

**Decision:** add in Phase 7.

### P2 — Quality polish

**5. `XS` Calibration buckets are inclusive on both ends.**
`CONFIDENCE_BUCKETS` uses `>= low and <= high`. The buckets `(0–49, 50–59, ...)` don't overlap because they're non-overlapping intervals, but a confidence of exactly 50 lands in the `50–59` bucket only (correct). However, if a future bucket were added that overlapped, the inclusive-both pattern would silently double-count. Add a code comment noting the assumption.

**6. `XS` Wilson CI hand-implementation: tested at boundaries (n=10, p=1.0)?**
The `_wilson_ci` function correctly clamps to `[0, 1]` (lines 65-66). Tested implicitly via the `test_perfect_agreement` test which produces p=1.0; no failures. Acceptable.

**7. `S` Streamlit UI lacks keyboard shortcuts.**
For a 6-8 hour labeling session, mouse-only navigation is fatiguing. Streamlit doesn't natively support hotkeys, but `streamlit-shortcuts` (third-party) or a `st.components.v1.html` script could add them. Defer — first pass through 80 rows will reveal whether this matters.

**8. `S` review_app.py allows previous/skip without saving the radio state.**
If labeler picks a label, types justification, then clicks "Previous" or "Skip" by mistake, the partial work is lost. Adding a "draft" autosave to session_state would help. Defer — the existing "Save & Next" requires explicit click, so no accidental data loss; just inefficient backtracking.

### P3 — Stretch / nice-to-have

**9. `M` Inter-rater reliability (Cohen's kappa).**
Only relevant if a second labeler gets involved. Not in scope for v1 eval (single-labeler is documented as a limitation in `LABELING_PROTOCOL.md`). Add the `cohen_kappa_score` import to `score.py` only if/when needed.

**10. `S` Double-stratification (status × confidence).**
Pure status stratification (current) catches "AI is biased toward one class." Adding confidence-bucket stratification within each status (5 from 90-100, 5 from 70-89, ...) would also reveal calibration failures. At n=80, this gives n=2.5 per cell — too small for stratum-level CI. Skip for v1.

---

## Apply now (Phase 4 polish, before Phase 5)

Implementing P0 (#1) only. Everything else deferred to Phase 7 or post-demo with documented justification.

## Implementation plan for #1

1. Add `--input-xlsx` flag to `sample.py` argparse.
2. When provided, after grouping/sampling, read the xlsx using openpyxl, build a dict `{row_index: {"city": ..., "state": ...}}`, join.
3. Add `city` and `state` columns to `OUTPUT_COLUMNS` (between `website` and `predicted_status`).
4. Update `review_app.py` display logic — already reads `row.get("city", "")` and `row.get("state", "")`, so no app-side change needed.
5. Update `test_sample.py` — add a test that uses an xlsx fixture and verifies city/state are populated.
6. Default behavior (no `--input-xlsx`): emit empty city/state with a logger warning, document in `LABELING_PROTOCOL.md` that "label without city/state is harder when business names are common."

## Verification after the fix

- `pytest business_checker/eval/tests/` → all green including new test
- `python3 -m eval.sample --checkpoint <smoke> --input-xlsx ../data/BMOSG_All_Businesses.xlsx --n-per-status 5` → produces sample with city/state populated
- `streamlit run eval/review_app.py -- --dataset <new-sample>` shows city/state under business name
