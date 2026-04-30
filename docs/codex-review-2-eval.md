# Codex Review #2 — Eval Design

**Date:** 2026-04-30
**Reviewers:**
1. Self-review by orchestrator (Claude Opus 4.7) — initial pass
2. **Codex CLI 0.117.0 (gpt-5)** — second pass, sandbox-safe prompt that explicitly instructed not to attempt subprocess execution. ~30k tokens, ~5 min wall time. Output at `/tmp/codex-review-2b.txt`.

**Note on first attempt:** An earlier Codex run (~40 min) hung when its sandbox repeatedly denied subprocess calls it tried to use for verification. Killed at 15:56. Re-issued with static-only prompt; second attempt succeeded.

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

---

## Codex review #2 findings (after the city/state fix was committed)

Codex was given the self-review above and asked to confirm or push back. Verbatim summary of its 6 answers:

1. **Headline metric:** Keep overall agreement, ADD macro-F1 as the co-headline. Agreed with self-review. (Macro-F1 penalizes both minority-class misses and overprediction; balanced accuracy fixes only recall imbalance; MCC is too opaque for leadership.)

2. **Sampling:** Agreed with punting on confidence double-stratification at n=80. (At 4 statuses × 4 confidence buckets = 16 cells, n=5 each, individual cells too small for any inference.)

3. **Wilson math:** Confirmed correct. For n=10, p=1.0 the lower bound resolves to ~0.722, matching expected.

4. **classification_report labels arg:** **Push-back.** Self-review used `present_labels` (filtering by appearance in the data). Codex argued: pass all 4 STATUS_LABELS with zero_division=0 always. Filtering hides absent classes — exactly the case leadership needs to see (e.g., "the AI never produced any 'No Web Presence' verdicts"). **Accepted and applied.**

5. **LABELING_PROTOCOL.md ambiguity:** Confirmed gaps for marketplace-native, food-truck, mobile/home-based, and e-commerce-only veteran businesses. Specifically, the "two channels within 24 months" Active rule is too strict for single-channel businesses. **Accepted and applied — added 4-section addendum to the protocol.**

6. **Other findings:**
   - **6a (real bug):** `quick_links` in review_app.py searches by name only, not name + city/state. Common-name businesses route to the wrong entity. **Fixed — Google + Maps + Facebook + LinkedIn now use `name + city + state`; Instagram still uses name-only because hashtag-style search doesn't benefit from location.**
   - **6b (defensive):** Neither sample.py nor score.py validate that predicted_status / human_label values are within the canonical 4 + Unable-to-Determine. The Pydantic schema in `tools/check_business.py` enforces this for new AI calls, but a corrupted CSV or future model swap could leak off-ontology values that silently skew metrics. **Fixed — added validation in score.py that raises ValueError on off-ontology values, with a clear error message naming the offending values.**

## Fixes applied this session

| Finding | File | Status |
|---|---|---|
| P0: city/state missing | `eval/sample.py`, output schema | ✅ shipped (commit 8ee2db9) |
| P1 #4: classification_report uses present_labels | `eval/score.py` lines 167-184 | ✅ shipped this commit |
| P1 #6a: quick_links missing location | `eval/review_app.py` | ✅ shipped this commit |
| P1 #6b: no off-ontology validation | `eval/score.py` | ✅ shipped this commit |
| P1 #5: LABELING_PROTOCOL gaps | `eval/LABELING_PROTOCOL.md` | ✅ shipped this commit |
| P1 #1: macro-F1 in headline | `eval/score.py` | ⏳ deferred to Phase 7 |
| P1 #2: bootstrap CI on per-status | `eval/score.py` | ⏳ deferred to Phase 7 |
| P1 #3: ECE single number | `eval/score.py` | ⏳ deferred to Phase 7 |

Phase 4 exits with these fixes shipped and 111 pytest tests passing. The deferred items are documented and tagged for Phase 7 — they're enhancements to the report layout, not blockers for the 80-row labeling work.
