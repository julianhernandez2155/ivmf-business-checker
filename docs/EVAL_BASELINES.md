# Eval Baselines — Canonical Reference

> **Purpose:** Single source of truth for iteration scores on the
> `bmosg_v1_eval_sample.csv` (60 rows, hand-labeled by Julian).
> Always compare new iterations against this table.
>
> **Rule of thumb:** Optimize against the **Reachable** subset, not the full
> set. The full set has a structural ceiling of ~75–80% decisive accuracy
> because 27 rows are unreachable without new tools (social scrapers,
> metadata passthrough). See [`2026-05-12-reachability-ceiling.md`](2026-05-12-reachability-ceiling.md).

---

## Headline numbers

| Subset | Iter 9 dec | Iter 10 dec | Iter 11 dec | Iter 12 dec | v11 fresh 2026-05-13 dec | Iter 9 hf | Iter 10 hf | Iter 11 hf | Iter 12 hf | v11 fresh 2026-05-13 hf |
|---|---|---|---|---|---|---|---|---|---|---|
| **Full eval (58 rows)** | 67.4% | 59.1% | **72.0%** | 68.8% | 66.0% | 4 | 9 | **5** | 7 | 8 |
| **Reachable only (31 rows)** | 85.2% | **95.8%** | 86.2% | 81.5% | 81.5% | 0 | 0 | **0** | 1 | 2 |
| Unreachable only (27 rows) | 42.1% | 15.0% | **52.4%** | 52.4% | n/a | 4 | 9 | 5 | 6 | n/a |
| **Unreachable-social only (16)** | 55.6% | 27.3% | **64.3%** | 61.5% | 57.1% | 2 | 6 | 3 | 4 | 4 |

**Iter 9 (2026-05-12):** Baseline 3-pass + judge + rule scorer, run on every row.
**Iter 10 (2026-05-12):** Tiered (`--verify-flagged`) — saves cost but regressed on unreachable-social rows.
**Iter 11 (2026-05-12):** Iter 10 architecture + Facebook recency signal via Apify on every row. ← **CURRENT BASELINE**
**Iter 12 (2026-05-12):** Iter 11 + metadata block + marketplace-residue rule + Google SERP FB fallback + Instagram fallback. **NET-NEGATIVE — DO NOT SHIP.**

**Iter 13 (2026-05-12) — Stabilization.** No new model behavior; frozen
`PipelineConfig` system pins every toggle, cache key includes website +
`pipeline_fingerprint`, both runners consume the same configs via
`--pipeline {v10,v11,v12_current_prod,v12_full}`. The iter-11 saved CSV
re-scores to **72.0% decisive / 5 harmful / reachable 86.2% / 0 reachable
harmful** — reproduced 2026-05-12 by the canonical `score()` after
extensions. See [`2026-05-12-iter13-stabilization-plan.md`](2026-05-12-iter13-stabilization-plan.md)
for the full plan; the shippable command below now points to `v11`.

**v11 fresh, 2026-05-13.** A2 gate fresh run of `--pipeline v11` against
the 60-row eval, scored against the original human labels: **66.0%
decisive / 8 harmful / reachable 81.5% / 2 reachable harmful** ($0.81
Perplexity, 60/60 rows, 0 errors). Outside the plan's
reproducibility band (decisive [69-75%], harmful ≤7). 21 of 60 verdicts
shifted vs. the iter-11 saved CSV — real Perplexity drift over 13 days.
Iter 14 must establish a new baseline before any new signal A/B is
meaningful; the saved iter-11 CSV is a 2026-04-30 snapshot, not a stable
model-behavior baseline. See the plan's "A2 result" section for the
full diagnosis.

**Key takeaways:**

- **Iter 11 remains the shippable baseline.** It is best on every subset except where iter 10 was already at-ceiling (reachable-only 95.8%).
- **Iter 12 was net-negative** despite adding 5 well-tested signals. Decisive dropped 72.0% → 68.8% (full set) and 86.2% → 81.5% (reachable). Reachable harmful flips went 0 → 1.
- **What went wrong in iter 12 (diagnosed 2026-05-12):**
  - **Travel Halo (correct in iter 11, wrong in iter 12):** Model trusted ZoomInfo's "2009-present, as of 2026" record over the FB-last-post-2020 dormant signal. The metadata block + marketplace-residue rule combined to confuse the verdict.
  - **Bundook (correct in iter 11, wrong in iter 12):** The IG tool extracted `bundookmilpackage` from the website footer and reported "recent post 2025-11-14" — but this brand never operationalized. IG handle from website HTML is not always the same brand.
  - **27 West, Back Office Administrations, One Fire Fight (all reachable, all flipped wrong):** Haiku judge over-applied skepticism after seeing the new evidence blocks; downgraded Active verdicts to Uncertain on businesses that iter 11 correctly auto-trusted.
- **The pattern:** adding more signals to the prompt gives the model more rope to hang itself with. Each new signal is reasonable in isolation; combined, they over-fire on edge cases and Perplexity (plus the judge) over-corrects.

**Recommendation:** Revert to iter 11 for the 709 production run. Investigate the 4 specific iter 12 failures in a future iteration before re-attempting any of these 5 signals.

## Shippable command (since iter 13)

```bash
# Production 709-row run — iter 11 frozen config (the documented shippable).
python run_checker.py --input ../data/BMOSG_All_Businesses.xlsx \
    --workers 3 --pipeline v11

# Eval rerun against the 60-row labeled sample — same v11 config.
python -m eval.rerun_sample --pipeline v11 \
    --sample eval/datasets/bmosg_v1_eval_sample.csv \
    --input-xlsx ../data/BMOSG_All_Businesses.xlsx \
    --out eval/reports/v11_fresh/predictions.csv

# Score a labeled CSV — emits decisive_accuracy, harmful flips (both
# directions), review_queue_size, and reachability slices.
python -m eval.score --labeled <labeled.csv> --out-dir eval/reports/<run>/

# Compare two configs side-by-side; exits non-zero on regression.
python -m eval.compare_configs \
    --baseline eval/datasets/bmosg_v1_iteration_10_tiered.csv \
    --candidate eval/datasets/bmosg_v1_iteration_11_fb.csv
```

The legacy `--enable-facebook-recency` / `--enable-instagram-fallback`
flags were hard-removed in iter 13 — invocations using them now error
with a migration message pointing at `--pipeline`.

---

## Reachability distribution (60 rows total)

| Category | Count | Share | What it means |
|---|---|---|---|
| **reachable** | 31 | 52% | Pipeline has the tools needed. |
| **unreachable-social** | 16 | 27% | Needs Facebook / Instagram / LinkedIn scraper. |
| **unreachable-judgment** | 8 | 13% | Even a human marked ambiguous. |
| **unreachable-metadata** | 3 | 5% | Needs "Date Added" column in prompt. |
| **unreachable-other** | 2 | 3% | Multi-hop browsing, business-model edge cases. |

---

## Definitions

- **Decisive accuracy** — when the system commits to a non-Uncertain verdict
  (Active / Likely Closed / NWP), is it right? Excludes hedged Uncertain
  predictions from both numerator and denominator.
- **Harmful flips** — predicted Active when human said Likely Closed, OR
  predicted Likely Closed when human said Active. These are the most
  expensive errors operationally (false outreach OR missed outreach).
- **Reachable** — given the current tool stack (Perplexity + scrape +
  rule scorer + Haiku judge), the decisive signal the human used to label
  this row is available to the pipeline.

---

## Source artifacts

- Row-by-row reachability tags: [`../business_checker/eval/datasets/bmosg_v1_reachability_tags.csv`](../business_checker/eval/datasets/bmosg_v1_reachability_tags.csv)
- Full analysis: [`2026-05-12-reachability-ceiling.md`](2026-05-12-reachability-ceiling.md)
- Iter 9 predictions: [`../business_checker/eval/datasets/bmosg_v1_iteration_9_tuned.csv`](../business_checker/eval/datasets/bmosg_v1_iteration_9_tuned.csv)
- Iter 10 predictions: [`../business_checker/eval/datasets/bmosg_v1_iteration_10_tiered.csv`](../business_checker/eval/datasets/bmosg_v1_iteration_10_tiered.csv)

---

## How to update this file

When a new iteration runs against the eval sample:

1. Score it with `python -m eval.score --labeled <labeled.csv> --out-dir eval/reports/<run>/`.
   The output `report.md` now contains decisive_accuracy, harmful flips
   (both directions), and per-reachability slices in a single pass —
   the legacy `score_by_reachability` step is no longer needed.
2. Add a new row to the headline table above. Pull "decisive" from the
   `decisive_accuracy` line in the report; pull harmful from
   `harmful_flips_total`. Reachable and unreachable-social splits live
   in the Slices table.
3. If the iteration introduces a new tool (e.g., Facebook scraper), update
   the reachability tags CSV to re-classify any newly-reachable rows.

**Do not delete prior rows.** This file is a longitudinal record.

---

## Open questions / future iterations

- **Iter 11 (DONE 2026-05-12):** Facebook recency tool via Apify.
  Result: unreachable-social decisive 27.3% → 64.3% (+37pp). Reachable
  harmful = 0 (no regression on the protected subset). Full harmful 9 → 5.
  Shipped as the new baseline.
- **Iter 12 (FAILED 2026-05-12):** Five-signal combination (metadata,
  marketplace-residue, FB no-found prompt fix, Google SERP FB fallback,
  IG fallback). All 5 unit-tested individually; combined effect was
  net-negative on the eval set. Code is shipped but the kwargs default
  to OFF — re-enabling requires explicit `--enable-instagram-fallback`
  etc. Future iteration must isolate which of the 5 caused regressions
  rather than re-enabling them in bulk.
- **Future iter (re-evaluate failures from iter 12):**
  - Travel Halo, GAP: marketplace-residue rule missed these (ZoomInfo
    + "as of 2026" should have been residue, but the rule's "no FB"
    safety condition didn't fire because FB *was* found, just dormant)
  - Bundook: IG handle from website HTML can be a different brand —
    need a name-match check before trusting site-extracted IG handles
  - 27 West, Back Office: Haiku judge needs tuning when many evidence
    sections are present — it's over-applying skepticism on
    information-rich prompts
- **Iter N (likely skip):** LinkedIn. Meta blocks scrapers aggressively,
  signal rarely decisive. Don't build unless eval data forces it.
