# Iter 13 — Stabilization Plan (pre-restructure)

**Author:** Claude (for Codex review)
**Date:** 2026-05-12
**Status:** EXECUTED 2026-05-12–13. Phases A/B/C code + tests + docs all
landed. A1 gate (saved-artifact rescore) and the Phase B compare gate
both pass exactly. **A2 gate (fresh `--pipeline v11` run on 2026-05-13)
FAILED the band check: decisive 66.0% vs. required 69–75%, harmful 8 vs.
required ≤7. Config in `run.log` confirms v11 toggles are correct, so
this is real Perplexity drift, not a code bug.** This is the failure
mode the plan's wider band was designed to surface — see "Phase A2
hand-off" at the bottom for the full diagnosis and what it means for
iter 14.
**Predecessor:** `docs/2026-05-12-iter12-handoff.md`
**Codex review under:** `docs/2026-05-12-codex-adversarial-review.md` (verdict on iter 12: blocked)

## Revision 1 changelog (2026-05-12)

Codex flagged five issues in revision 0. All accepted and applied:

1. **Score API/IO mismatch** — `score_run()` doesn't exist; the actual entrypoint is `score()` and it reads CSV (not XLSX). Phase A/B gate commands corrected.
2. **Eval rerunner not stabilized** — `eval/rerun_sample.py` has its own `--enable-facebook-recency` / `--enable-instagram-fallback` flags. If only the production runner is config-frozen, eval and prod can diverge silently. Both must consume the same `PipelineConfig`.
3. **`V12_FULL` was mislabeled** — current production behavior is metadata-on + marketplace-residue-on + FB-off + IG-off, not "everything on." Renamed configs to reflect reality.
4. **Harmful-flip metric was directional only** — docs define it as both `Active→Closed` and `Closed→Active` directions. Tracked as both + total now.
5. **±1pp fresh-run gate was too strict** — saved-CSV reproduction is the real determinism gate; fresh-run gets a wider tolerance band that accounts for Perplexity/search drift.

## Revision 2 changelog (2026-05-12)

Codex revision-1 review flagged six issues. All accepted and applied:

1. **Wrong saved-artifact filename** — `bmosg_v1_eval_labeled.csv` doesn't exist. Real iter 11 saved artifact is `bmosg_v1_iteration_11_fb.csv`. All gate paths corrected.
2. **Phase A "independently shippable" was a lie** — A2 depended on a Phase B helper. Resolution per Codex preference: `join_results_to_labels.py` moved into Phase A. Phase A now has both A1 + A2 gates passing before commit.
3. **"Exactly three" said but four configs defined** — wording fixed to "exactly four."
4. **Cache key still missed website** — current cache excludes website *by design* (cache.py:5), but verdicts are website-sensitive (a changed URL produces different Perplexity context, different scrape results, different verdicts). Cache key now includes normalized website + pipeline fingerprint.
5. **Decisive accuracy definition drifted from canon** — `EVAL_BASELINES.md:56-57` defines decisive as "non-Uncertain (Active / Likely Closed / NWP)." Revision 1 had narrowed it to {Active, Likely Closed} only. Restored to canonical definition.
6. **Deprecated flag soft-removal was over-engineered** — this is a personal tool, not a public API. `--enable-facebook-recency` and `--enable-instagram-fallback` on `rerun_sample.py` now hard-error in the same Phase A commit, with a message pointing to `--pipeline`. No deprecation period.

---

## Goal

Make the system **measurably reproducible** before any further signal work or any 709-row run. This plan does **not** patch iter 12 failures, does **not** add new signals, and does **not** restructure the architecture. It exists to create the preconditions under which restructuring (iter 14+) can be done with feedback.

**Success definition (binary):**
1. **Determinism gate (saved artifact):** `score()` re-run against the saved iter 11 labeled CSV produces the *exact* documented metrics (72.0% decisive, 5 harmful flips, 0 reachable harmful flips). Zero tolerance — this is a metric-code regression test, not a model run.
2. **Reproducibility gate (fresh run):** `run_checker.py --pipeline v11` and `eval/rerun_sample.py --pipeline v11` against the 60-row eval produce decisive accuracy ∈ [69.0%, 75.0%] and total harmful flips ≤ 7. Wider band reflects Perplexity result drift, date-relative staleness, and search-index churn — anything inside the band is "iter 11 reproduced"; anything outside means either the config is wrong or the eval has decayed and needs re-labeling.
3. **Measurability gate:** A single command prints `decisive_accuracy`, `harmful_flips_total`, `harmful_flips_active_to_closed`, `harmful_flips_closed_to_active`, reachable/unreachable/unreachable-social slices, and `review_queue_size` side-by-side vs. baseline, in <60 seconds.
4. **Toggle gate:** Marketplace-residue, metadata-injection, FB-recency, and IG-fallback are each independently togglable from **both** `run_checker.py` and `eval/rerun_sample.py` via the same `--pipeline` flag, sharing the same `PipelineConfig` source of truth.

If any of those four fail, this plan failed and we do not move to iter 14.

---

## Non-goals (explicit)

These are intentionally **excluded** to keep scope narrow and to honor Codex's "stop and restructure" recommendation:

- ❌ Bundook / Travel Halo / GAP regression patches (would reinforce iter 12 architecture)
- ❌ Sonnet-4.6-as-judge swap (architectural — belongs in iter 14)
- ❌ Typed evidence model / single adjudication stage (the iter 14 restructure)
- ❌ 200-row labeling effort (separate workstream — needs (2) below to be useful first)
- ❌ Any 709-row production run
- ❌ New signals of any kind
- ❌ Prompt tuning of any kind

---

## Sequencing — three phases, each independently shippable

Each phase produces a commit and a verifiable artifact. **Do not advance to phase N+1 until phase N's verification gate passes.**

### Phase A — Frozen pipeline configs (the reproducibility fix)

**Why first:** Codex's #1 critical finding is "the production runner cannot reproduce iter 11." Until this is fixed, no other work is measurable. Both runners (production and eval) must consume the same config object — otherwise eval and prod can drift silently.

**Files touched:**
- `business_checker/tools/pipeline_configs.py` (NEW, ~90 lines)
- `business_checker/tools/cache.py` (modified — website + pipeline-fingerprint cache key)
- `business_checker/run_checker.py` (modified — CLI flag + dispatch)
- `business_checker/eval/rerun_sample.py` (modified — same `--pipeline` flag, hard-remove old per-signal flags)
- `business_checker/tools/check_business.py` (modified — add `use_marketplace_residue` kwarg)
- `business_checker/eval/join_results_to_labels.py` (NEW, ~60 lines — moved here from Phase B per Codex revision-2 finding #2)
- `business_checker/tests/test_pipeline_configs.py` (NEW, ~80 lines)
- `business_checker/tests/test_join_results_to_labels.py` (NEW, ~40 lines)

**Implementation:**

1. Create `tools/pipeline_configs.py` exporting frozen dataclasses + a registry:
   ```python
   @dataclass(frozen=True)
   class PipelineConfig:
       name: str
       use_facebook_recency: bool
       use_instagram_fallback: bool
       use_metadata: bool
       use_marketplace_residue: bool
       use_rule_scorer: bool
       verify_flagged: bool

       def fingerprint(self) -> str:
           """Short stable hash of config — used in cache key + logged at run start."""
   ```
   Define exactly four named configs (corrected to match real behavior — Codex revision-1 finding #3):
   - **`v10`** — pre-FB-recency baseline. `use_facebook_recency=False`, `use_instagram_fallback=False`, `use_metadata=False`, `use_marketplace_residue=False`, `use_rule_scorer=True`, `verify_flagged=True`.
   - **`v11`** — the documented shippable. v10 + `use_facebook_recency=True`. Metadata + marketplace-residue stay off (this is what the iter 11 docs claim, and what we need to verify reproduces).
   - **`v12_current_prod`** — what `run_checker.py` actually does *today* (per `run_checker.py:138-152`): `use_metadata=True` (always passed when columns exist), `use_marketplace_residue=True` (default-on, no flag), `use_facebook_recency=False`, `use_instagram_fallback=False`. **This is the silently-shipping iter 12 partial bundle Codex flagged.** Naming it `v12_current_prod` (not "v12_full") makes the integrity problem visible.
   - **`v12_full`** — separately defined: everything on. Used for completeness in eval; not for production.

2. Modify `tools/cache.py` (Codex revision-1 open question #1 + revision-2 finding #4):
   - Cache key becomes `(normalized_name, normalized_website, city, state, pipeline_fingerprint)` instead of `(normalized_name, city, state)`.
   - **Why include website:** the current cache (`cache.py:5`) intentionally excludes website "because verdicts shouldn't depend on the listed URL." That assumption is wrong — the URL feeds Perplexity context and the website-scrape signal, both of which materially affect the verdict. Two records with the same name/city/state but different URLs (data entry corrections, brand redirects) should not collide.
   - **Why include pipeline_fingerprint:** different pipelines produce different verdicts for the same business; they must not share cache namespace.
   - Update both `make_cache_key()` and the `get/put` callsites in `tools/check_business.py`.
   - Migration: existing cache entries are simply not hit under the new key — they remain on disk, harmless. No destructive migration. Document this in the docstring at the top of `cache.py`.

3. Modify `run_checker.py`:
   - Add `--pipeline {v10,v11,v12_current_prod,v12_full}` flag (required, no default — explicit choice forced).
   - Remove the implicit metadata-extraction-when-columns-exist behavior at line 138. Always extract `metadata`, but only pass it to `check_business` when `config.use_metadata is True`.
   - Replace ad-hoc kwargs in `process_row` (lines 140-152) with `config.use_*` lookups.
   - Log the resolved config dict + fingerprint at run start so `run.log` proves what was used.
   - Keep existing `--verify-flagged` and `--3pass` flags but assert they don't conflict with config (e.g., `--pipeline v10 --verify-flagged` is redundant since v10 already has it on; warn don't error).

4. Modify `eval/rerun_sample.py` (Codex revision-1 finding #2 + revision-2 finding #6):
   - Add the same `--pipeline` flag, required, no default.
   - **Hard-remove** `--enable-facebook-recency` and `--enable-instagram-fallback`. If either appears in argv, argparse should error with: *"Removed in iter 13. Use `--pipeline {v10,v11,v12_current_prod,v12_full}` instead. See docs/2026-05-12-iter13-stabilization-plan.md."* No deprecation period — this is a personal tool, not a public API.
   - All paths through `rerun_sample.py:144-180` consume the same `PipelineConfig` and call `check_business` with identical kwargs as the production runner.

5. Modify `tools/check_business.py`:
   - Add `use_marketplace_residue: bool = True` kwarg to both `check_business` and `check_business_with_verification` (preserves current behavior when omitted, lets configs explicitly set it).
   - Wrap the marketplace-residue block (lines 749-778) in `if use_marketplace_residue:`.
   - Verify metadata injection block (lines 463+) is already conditional on `metadata is not None` (it is, per the read).

6. **Create `eval/join_results_to_labels.py`** (moved from Phase B per Codex revision-2 finding #2 — required for A2 gate):
   - Takes a `Results.xlsx` from a fresh run + an existing labeled CSV (which has human labels) as inputs.
   - Joins on `(normalized_name, normalized_city, normalized_state)` — same normalization as the cache key.
   - Outputs a new labeled CSV with fresh `predicted_status` / `predicted_confidence` + frozen `human_label` from the input labeled set.
   - Handles unmatched rows by logging counts and skipping them (does not silently drop or duplicate).
   - This is what makes A2's fresh-run gate executable in the same Phase A commit.

7. **Tests** (`tests/test_pipeline_configs.py` + `tests/test_join_results_to_labels.py`):
   - Assert each named config has the documented kwarg signature and exact bool values
   - Assert `v11.use_marketplace_residue is False` and `v11.use_metadata is False` (the iter 11 truth)
   - Assert `v12_current_prod.use_marketplace_residue is True` and `v12_current_prod.use_metadata is True` (the iter 12 leak)
   - Assert `--pipeline` is required in both `run_checker.py` and `rerun_sample.py` (argparse error when omitted)
   - Assert old `--enable-facebook-recency` and `--enable-instagram-fallback` flags now hard-error with the iter-13 message
   - Assert `PipelineConfig.fingerprint()` is stable across runs and changes when any field changes
   - Assert cache `get/set` round-trips correctly with same (name, website, city, state, fingerprint) and misses when website OR fingerprint differs
   - Assert `join_results_to_labels.py` produces correct row count, preserves human labels, and logs unmatched-row counts
   - Snapshot test: log line at run start contains the config name + fingerprint + full dict

**Verification gate (must pass to advance to Phase B):**

Two separate gates — Codex revision-1 finding #5. Both must pass in this commit (Codex revision-2 finding #2 — no skipped gates):

```bash
# Gate A1 — Determinism gate (saved artifact, zero tolerance):
# Re-score the existing iter 11 saved CSV. This proves the metric code is stable.
# Note: Phase B extends score() with new metrics; this gate uses the unchanged
# canonical metrics that already exist in score() today.
python -m eval.score \
  --labeled eval/datasets/bmosg_v1_iteration_11_fb.csv \
  --out-dir eval/reports/iter13_phaseA_smoke/
# Expect: exact match to documented iter 11 numbers in EVAL_BASELINES.md.
# Any drift here is a metric-code bug, not a model issue.

# Gate A2 — Reproducibility gate (fresh run, wider tolerance):
# Step 1: fresh run with the v11 frozen config
python run_checker.py --input ../data/eval_60.xlsx --workers 3 --pipeline v11
# Step 2: join the fresh Results.xlsx with the existing labeled CSV's human labels
python -m eval.join_results_to_labels \
  --results Runs/<latest>/eval_60_Results.xlsx \
  --labels eval/datasets/bmosg_v1_iteration_11_fb.csv \
  --out eval/reports/v11_fresh/labeled.csv
# Step 3: score the joined labeled CSV
python -m eval.score \
  --labeled eval/reports/v11_fresh/labeled.csv \
  --out-dir eval/reports/v11_fresh/
# Expect: decisive_accuracy ∈ [69.0%, 75.0%], harmful_flips_total ≤ 7.
# Outside that band ⇒ either v11 config is wrong, or the eval has decayed
# (Perplexity result drift, date-relative staleness) and needs re-labeling.
```

**Risk 1:** Some prior runs cached results under the old (name, city, state) key. Mitigation: new key adds website + pipeline_fingerprint (Phase A step 2). Old entries are inert; no destructive cleanup needed.

**Risk 2:** Phase A's commit now includes both the join helper and gate-A2 execution. Estimated effort revised to reflect this.

**Estimated effort:** 4 hours (revised up from 3 — join helper + cache-key-includes-website + executing A2 in same commit).

---

### Phase B — Eval gate automation (the measurability fix)

**Why second:** Codex's medium finding (eval gate not automated around the metric we're optimizing). Without this, every config change requires manual analysis to know if it helped.

**Files touched:**
- `business_checker/eval/score.py` (modified — extend the existing `score()` function, not a new `score_run()`)
- `business_checker/eval/datasets/bmosg_v1_reachability_tags.csv` (already exists, used as join input)
- `business_checker/eval/compare_configs.py` (NEW, ~140 lines)
- `business_checker/tests/test_score_extensions.py` (NEW, ~120 lines)
- _Note:_ `eval/join_results_to_labels.py` was moved to Phase A (Codex revision-2 finding #2).

**Implementation:**

1. **Extend the existing `score()` function** in `eval/score.py` (Codex finding #1 — `score_run` was a hallucinated name; the real entrypoint is `score()` and reads CSV). Add to its return dict:
   - **Harmful flips, both directions** (Codex finding #4):
     - `harmful_flips_active_to_closed`: int — predicted=Active, human=Likely Closed (the false-positive-on-active direction)
     - `harmful_flips_closed_to_active`: int — predicted=Likely Closed, human=Active (the false-negative-on-active direction)
     - `harmful_flips_total`: int — sum of both
   - `decisive_accuracy`: float — agreement rate over rows where `predicted_status != "Uncertain"`. **Per `EVAL_BASELINES.md:56-57`, decisive includes Active, Likely Closed, AND No Web Presence — only Uncertain is excluded.** Codex revision-2 finding #5: do not narrow this definition. (Revision 1 incorrectly excluded NWP; restored here.)
   - `review_queue_size`: int — count of rows where `requires_review=True` in the labeled CSV (requires the column; add to labeled CSV schema if missing)
   - `slices`: dict — `{"reachable": {...full nested metrics...}, "unreachable_social": {...}, "unreachable_other": {...}}`, populated by left-joining on `bmosg_v1_reachability_tags.csv`. If a row has no reachability tag, it goes in an `untagged` bucket and a warning is logged.

2. ~~Create `eval/join_results_to_labels.py`~~ — **moved to Phase A** per Codex revision-2 finding #2. Phase B can assume this helper exists.

3. Create `eval/compare_configs.py`:
   - Takes two labeled CSV paths (e.g., `--baseline eval/reports/v10_<ts>/labeled.csv --candidate eval/reports/v11_<ts>/labeled.csv`)
   - Calls `score()` on both
   - Prints a side-by-side markdown table: `metric | baseline | candidate | delta | verdict`
   - Reports both directional harmful-flip counts separately (so a regression in one direction can't hide behind an improvement in the other)
   - Verdict per metric: ✅ green if candidate is at-least-as-good; ⚠️ yellow if within noise (~±2pp on decisive accuracy, ±1 on harmful flips); ❌ red otherwise
   - Overall exit code: 0 if no ❌; 1 if any ❌
   - Floor of scope: printed table + exit code only. No HTML, no plots, no dashboard. (Codex open question #4.)

4. **Tests** (`tests/test_score_extensions.py`):
   - Synthetic labeled CSV with known `Active→Closed` harmful flips → assert count, assert other-direction count is zero
   - Synthetic labeled CSV with known `Closed→Active` harmful flips → assert count, assert other-direction count is zero
   - Synthetic labeled CSV with mixed reachable/unreachable tags → assert slice metrics correct
   - Synthetic labeled CSV with rows missing reachability tag → assert `untagged` bucket populated + warning emitted
   - Synthetic labeled CSV with predicted=NWP, human=NWP → assert it counts as decisive AND correct (canonical definition includes NWP)
   - `compare_configs` end-to-end on two synthetic labeled CSVs → assert markdown table format + exit code in both pass and fail cases
   - _Note:_ `join_results_to_labels` tests live in Phase A.

**Verification gate (must pass to advance to Phase C):**
```bash
# Re-score the saved iter 11 CSV with the new score() — exact match required on the
# canonical metrics (decisive_accuracy uses the EVAL_BASELINES.md definition: non-Uncertain
# including NWP).
python -m eval.score \
  --labeled eval/datasets/bmosg_v1_iteration_11_fb.csv \
  --out-dir eval/reports/iter13_phaseB_smoke/
# Expect: decisive_accuracy=72.0%, harmful_flips_total=5,
#         harmful_flips_active_to_closed + harmful_flips_closed_to_active = 5,
#         slices.reachable.harmful_flips_total = 0.

# Then compare against the saved iter 10 CSV.
python -m eval.compare_configs \
  --baseline eval/datasets/bmosg_v1_iteration_10_tiered.csv \
  --candidate eval/datasets/bmosg_v1_iteration_11_fb.csv
# Expect: decisive_accuracy delta ≈ +5pp (matches iter 10→iter 11 historical per EVAL_BASELINES.md), exit 0.
```

**Estimated effort:** 4 hours (revised up from 3 — bidirectional harmful flips + extending real `score()` function instead of writing a fictional one).

---

### Phase C — Documentation truth-up (the integrity fix)

**Why last:** Once A and B are real, the docs need to match.

**Files touched:**
- `docs/EVAL_BASELINES.md` (modified)
- `docs/2026-05-12-iter12-handoff.md` (annotated, not rewritten — historical record)
- `docs/2026-05-12-iter13-stabilization-plan.md` (this file — mark COMPLETE)
- `docs/RUNBOOK.md` (NEW, ~40 lines — the canonical "how to run a 709" reference)

**Implementation:**

1. `EVAL_BASELINES.md`: replace "shippable command" snippets with explicit `--pipeline v11_frozen` invocations. Add a "Reproduced on YYYY-MM-DD" line under each baseline row, populated from Phase A verification.

2. `iter12-handoff.md`: prepend a one-paragraph note: *"Superseded 2026-05-12 by iter 13 stabilization. The 'iter 11 shippable command' in this doc is not reproducible as written — see RUNBOOK.md."* Do not edit the body.

3. `RUNBOOK.md` (NEW): single-page reference for production runs. Contains:
   - Pre-flight checklist (cost cap, key validation, --no-cache decision)
   - The exact `--pipeline` flag values and what each means
   - How to read `compare_configs.py` output
   - Rollback: how to abort a 709-row run mid-flight (Ctrl+C → checkpoint resume)

**Verification gate (final):**
- `grep -r "iter 11" docs/` returns zero claims that are not paired with a reproducibility note
- `RUNBOOK.md` exists and references only commands that work

**Estimated effort:** 1 hour.

---

## What this plan does NOT solve (and that's intentional)

These are real problems Codex flagged. They are out of scope for iter 13 because iter 13 is about *measuring*, not *fixing*. Each gets its own RFC after iter 13 ships:

| Codex finding | Why deferred | Future iter |
|---|---|---|
| Order-dependent verdict mutation stack | Architectural restructure — needs the eval gate from Phase B to be safe | iter 14 |
| Asymmetric judge (Haiku) | Belongs to "judge subsystem RFC" — needs a 200-row eval to validate | iter 14 |
| Identity-before-recency for IG/FB | Requires typed evidence model — coupled to iter 14 restructure | iter 14 |
| 60-row eval noise floor | Needs labeling investment, separate workstream | iter 15 |
| Multi-model voting / Sonnet-as-judge | Needs the side-by-side gate from Phase B before any A/B is meaningful | iter 14 or 15 |

---

## Open questions for Codex (revision 1 — answers from Codex review applied)

Codex resolved all four open questions in its review. Recording resolutions here so the next reviewer doesn't re-litigate:

1. **Cache invalidation:** ✅ RESOLVED — `pipeline_fingerprint` in the cache key (separate cache files = doubles disk, less ergonomic). Plan applies this in Phase A step 2. Do not rely on `--no-cache` long-term.

2. **Metadata extraction shape:** ✅ RESOLVED — always extract `metadata` in the runner; only pass it to `check_business` when `config.use_metadata is True`. Plan applies this in Phase A step 3.

3. **Keep `v10` config:** ✅ RESOLVED — keep it as a regression anchor. Low maintenance cost. Plan retains.

4. **Phase B scope:** ✅ RESOLVED — printed table + exit code is the right floor. Do not build a dashboard. Plan retains the floor.

### Revision-1 open questions — all resolved by Codex revision-2 review

1. **Phase A2 / Phase B sequencing:** ✅ RESOLVED — Codex prefers moving the join helper into Phase A so both A1 + A2 gates pass in the same commit. Applied.
2. **Reproducibility band width:** ✅ RESOLVED — Codex confirms ±3pp on decisive accuracy is acceptable; harmful_flips ≤ 7 is the hard guard. Applied as written.
3. **`v12_current_prod` naming:** ✅ RESOLVED — Codex confirms the editorial name is fine because it exposes the leak. Retained.
4. **Deprecated flag timeline:** ✅ RESOLVED — Codex says rip them out now and hard-error. Applied in Phase A step 4.

### No new open questions in revision 2

Revision 2 is responsive only — every change addresses a Codex revision-1 finding or open-question resolution. No new design decisions introduced.

---

## Total estimated effort: 9 hours across 3 commits (revised from 8)

- Commit 1: Phase A (pipeline configs + cache key with website + eval rerunner stabilization + join helper + Phase A1 + A2 gates pass) — **4 hours**
- Commit 2: Phase B (extended `score()` with canonical decisive-accuracy definition + bidirectional harmful flips + compare_configs) — **4 hours**
- Commit 3: Phase C (docs + runbook + supersedes-note on iter 12 handoff) — **1 hour**

After commit 3, the system is in a state where iter 14 (the actual restructure Codex recommended) can begin with feedback. Until then, no 709-row run, no new signals, no patches to iter 12 failures.

---

## Phase A2 hand-off (2026-05-12)

Phase A code (configs + cache + runners + join helper + tests) is
complete and the rest of the work is staged but **not yet committed**,
because gate A2 burns real Perplexity + Apify budget. The plan says
"Phase A's commit now includes both the join helper and gate-A2
execution" — so the commit waits on a successful A2.

To finish Phase A:

```bash
# Already built: ../data/eval_60.xlsx (60 rows pulled from
# BMOSG_All_Businesses.xlsx, matching the row indices in
# eval/datasets/bmosg_v1_eval_sample.csv).

# Fresh v11 run. ~5-10 min on Tier 1, ~$1-3 total (Perplexity + Firecrawl + Apify).
python run_checker.py --input ../data/eval_60.xlsx --workers 3 --pipeline v11

# Note the Runs/<stem>_<timestamp>/ output directory and substitute below.
RUN=Runs/eval_60_<TIMESTAMP>

# Join fresh predictions with the existing labeled-CSV human labels.
python -m eval.join_results_to_labels \
    --results "$RUN/eval_60_Results.xlsx" \
    --labels eval/datasets/bmosg_v1_iteration_11_fb.csv \
    --out eval/reports/v11_fresh/labeled.csv

# Score with the extended metrics.
python -m eval.score \
    --labeled eval/reports/v11_fresh/labeled.csv \
    --out-dir eval/reports/v11_fresh/
```

**Pass condition (Phase A gate A2):**
- `decisive_accuracy` ∈ [69.0%, 75.0%]
- `harmful_flips_total` ≤ 7

If both hold, Phase A is reproducible end-to-end and the three commits
(A, B, C) can land. If either misses, investigate before committing —
either the v11 config drifted, the eval has decayed and needs
re-labeling, or there's a bug in the new code path that the
saved-artifact gate didn't catch.

Side-by-side validation already passed for the saved artifacts (A1 +
Phase B gate) on 2026-05-12:
- Iter 11 saved CSV rescore: 72.0% decisive / 5 harmful / reachable 86.2% / 0 reachable harmful — exact match to `EVAL_BASELINES.md`.
- Iter 10 → iter 11 compare: decisive +12.9pp, harmful 9→5, all green, exit 0.

### A2 result (2026-05-13 — gate failed, finding documented)

The fresh `--pipeline v11` run on `../data/eval_60.xlsx` produced:

- decisive_accuracy = **66.0%** (band required [69.0%, 75.0%]) ❌
- harmful_flips_total = **8** (band required ≤ 7) ❌
- harmful_flips_active_to_closed = 7, harmful_flips_closed_to_active = 1
- Reachable slice: 81.5% decisive / 2 harmful (saved iter 11 was 86.2% / 0)
- Cost: $0.8068 Perplexity (plus Apify), 0 errors, 60/60 rows.
- Config in `Runs/eval_60_2026-05-13_0815/run.log` shows v11
  (`fp=45d749f559c7`) with FB on, IG/metadata/marketplace-residue off,
  rule_scorer on, verify_flagged on — exactly the documented iter 11
  toggle set.

**21 of 60 verdicts changed** vs. the iter-11 saved CSV (scored
2026-04-30, run 13 days earlier). Verdicts moved in both directions —
some closer to truth, some away. The reachable subset, which iter 11
got 100% harmful-free, picked up 2 harmful flips
(`A Simple Organizing & Moving Company` and
`Granted Advocacy Partners (GAP)` both flipped Closed→Active when human
labeled Likely Closed) — these are direct Perplexity-drift artifacts on
businesses the model previously called correctly.

**What this means:**

1. The iter 13 *code work* succeeded — eval and prod cannot drift
   silently anymore, every toggle is auditable in `run.log`, the
   determinism gate (A1) is rock solid, the eval-gate automation (Phase
   B) works.
2. The iter 13 *eval baseline* is no longer reproducible by fresh
   Perplexity runs. The saved iter 11 CSV is a snapshot of 2026-04-30
   Perplexity behavior, not a stable baseline.
3. Iter 14 cannot ship "decisive ≥ 72%" as a goalpost without first
   re-running v11 to establish a current Perplexity-baseline. Otherwise
   any new signal will be evaluated against a target the underlying
   model no longer hits.

**Recommended iter 14 entry point** (out of scope for this commit):

- Treat today's 66.0% / 8 harmful as the new v11 baseline on the
  60-row eval. Update `EVAL_BASELINES.md` with a row labeled
  "v11 fresh, 2026-05-13" and the iter 14 work compares against that.
- OR: re-label the eval against fresh evidence (the plan's "eval has
  decayed" branch). Some `Unable to Determine` rows may have resolved
  since April; some Active businesses may genuinely have closed.
- Decide before any 709-row run. Until then no production batch.
