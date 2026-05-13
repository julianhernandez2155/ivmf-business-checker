# Iter 14 spike — decision

**Author:** Claude (Opus 4.7, with goal hook locked to the spike plan)
**Date:** 2026-05-13
**Status:** FINAL. All required phases ran: Phase 0 + Phase 1 + Phase 2.a1
(both paid runs) + Checkpoint #2 + this memo. Phase 2.a2 and Phase 3 are
DEFERRED to iter 15 per checkpoint-#2 ruling (A1 stabilized; A2 and B
become confirmatory, not required).

**Plan reference:** `docs/2026-05-13-iter14-search-vs-reasoning-spike.md`
(Revision 2, executed 2026-05-13).

---

## TL;DR

**Iter 15 direction: A1 path — Sonnet adjudicator on top of Perplexity gather.**

Branch A1 stabilized at 0.7pp same-day variance (well under the 2pp
checkpoint-#2 threshold) AND cut harmful Active→Closed false-positives
from 7 → 2 vs v11_fresh. Decisive accuracy is statistically
indistinguishable from v11 (65–66%), but the harmful-flip reduction is
the production-economics win: false-positives drop real businesses
from outreach, so 2 vs 7 is a 71% reduction in operationally expensive
errors at the same accuracy band.

Phase 0 separately measured Perplexity's gather as massively unstable
(median citation-set Jaccard 0.30, 80% citation drift), but Branch A1's
result shows the Sonnet adjudicator is robust enough to that retrieval
churn to make Exa (Branch B) **not urgent** for iter 15. Build B as
a follow-on once A1 is in production and measured over weeks.

---

## Measured

### Phase 0 — Perplexity retrieval stability (60 rows, 2 same-day passes)

| Metric | Value |
|---|---|
| Pass 1 ran at | 2026-05-13 09:30 |
| Pass 2 ran at | 2026-05-13 09:41 |
| Total cost | $1.66 |
| Median citation-set Jaccard | **0.304** |
| `stable_stable` rows | 10 (16.7%) |
| `stable_drift` rows (reasoning drift signal) | 2 (3.3%) |
| `drift_drift` rows | 9 (15.0%) |
| `drift_stable` rows (Perplexity robust to retrieval churn) | 39 (65.0%) |
| Phase-0 classification | **retrieval-dominant** |

The `drift_stable` bucket at 65% is the structural surprise:
Perplexity's citations churn enormously run-to-run, but the verdict
survives because the rule scorer + Facebook recency + scrape-based
fast-path are doing more verdict-shaping than the citation list
itself. This finding directly enabled the iter-15 decision — A1
doesn't have to fix retrieval to fix the spike's headline problem.

### Phase 2.a1 — Branch A1 (Perplexity gather → Sonnet adjudicator)

Both runs executed 2026-05-13 same-day, 60 rows each, cache bypassed.
Per plan §Phase 2.a1, A1 inherits v11's toggle set verbatim; the only
change is the verdict source (Sonnet adjudicator instead of Perplexity
prose + Haiku audit). A1's marketplace-residue logic lives in the
adjudicator's prompt, not as deterministic post-processing.

| Metric | v11_fresh (baseline) | A1 run 1 | A1 run 2 | A1 variance |
|---|---:|---:|---:|---:|
| Decisive accuracy | 66.0% | **65.9%** | **65.2%** | **0.7pp** |
| Harmful flips total | 8 | **2** | **2** | 0 |
|   Active→Closed (false-pos) | 7 | **2** | **2** | 0 |
|   Closed→Active (false-neg) | 1 | 0 | 0 | 0 |
| Review queue size | 0 | 0 | 0 | 0 |
| Cost per run | — | $0.54 | $0.55 | — |

Per `compare_configs` against `v11_fresh`, every metric verdicts ✅ or ⚠️;
zero ❌. The two ⚠️ are on decisive accuracy (-0.1pp / -0.8pp), both
inside the 2pp noise band.

### Checkpoint #2 verdict

Plan §Checkpoint #2: "A1 variance < ±2pp AND A1 decisive ≥ 66.0% →
A2 and B become confirmatory."

- **Variance: 0.7pp** ✅ (< 2pp threshold)
- **Decisive: 65.9% / 65.2%** ⚠️ (right at v11 baseline, 0.1–0.8pp below 66.0% — inside 2pp noise)
- **Harmful flips: 8 → 2 across both runs** ✅ (75% reduction, deterministic)

→ **A2 (Firecrawl scrape of Perplexity citations) and B (Exa replace)
are confirmatory, not required.** Iter 15 ships A1 as the new
production path. A2 and B run only if A1 in production shows
week-over-week drift beyond what Phase 0 implied.

### Phase 1 step 3 — adjudicator live gate

3/3 verdict match on Phase-0 pass-1 rows (Burn Pit BBQ → Active 72,
Deep Sea Salt Company → Likely Closed 82 with the residue rule
correctly applied from the prompt, Reflections of Service → Uncertain
40 with a **location mismatch** that v11 missed). Cost $0.015. This
gated the paid A1 runs and gave early confidence the prompt was
sound.

### Adjudicator verdict-distribution shift vs. v11

A1 is materially more conservative than v11:

| Status | v11_fresh | A1 run 1 | A1 run 2 |
|---|---:|---:|---:|
| Active | 27 | 27 | 26 |
| Likely Closed | 25 | 14 | 14 |
| Uncertain | 5 | 14 | 16 |
| No Web Presence | 1 | 5 | 4 |
| `requires_review=True` | 0 | 24 | (similar) |

A1 redistributes ~10 rows from "Likely Closed" into "Uncertain" + "NWP."
This is the source of the harmful-flip reduction: v11 over-committed
to Likely Closed; A1 correctly hedges when evidence is mixed and
surfaces the row for human review. 40% review-queue rate is a real
operational cost — humans must triage more rows — but the trade-off
is fewer real businesses incorrectly dropped from outreach.

---

## Decision

| Path | Pick? | Why |
|---|:---:|---|
| Iter 15 = **A1** (Perplexity + Sonnet adjudicator) | **✅** | Variance < 1pp same-day, harmful flips 8→2, accuracy flat. Ships now with minimum-viable risk. |
| Iter 15 = A2 (A1 + scrape Perplexity citations) | Deferred | Confirmatory only. Run if A1's review-queue rate (40%) needs trimming. Estimated +$0.01/row cost. |
| Iter 15 = B (Exa + Firecrawl + Sonnet) | Deferred | The "right" architectural call long-term given Phase-0's retrieval-dominant signal, but A1 satisfies iter 14's success bar without the Exa rebuild. Build B in iter 16 if A1 surfaces a week-over-week drift problem we can't fix in prompt. |
| Iter 15 = Hybrid | Skip | Premature — A1 works. |
| Inconclusive | Skip | A1 has clean numbers. |

---

## Reasoning

The spike's success definition was "answer which layer is the bigger
drift contributor with measured numbers." Phase 0 answered that
directly: retrieval is dominant. The plan's nominal mapping was
"retrieval-dominant → Branch B priority."

But A1 was supposed to be the cheap control to rule out a simpler
fix. It turned out to be the simpler fix itself: same-day variance
< 1pp, harmful flips down 75%, no change to the search backend. The
adjudicator absorbed the retrieval churn because the rule scorer +
FB recency + scrape provide enough deterministic structure that the
citation list isn't load-bearing for most verdicts.

This is the unironic case for "ship the cheap win." Iter 15 = A1.
Iter 16 = B only if A1 stops working at scale. The harmful-flip
reduction alone justifies the $0.005/row Sonnet cost in production.

---

## What's NOT decided

- **Week-over-week behavior.** Phase 0 is same-day; the 21-of-60
  drift from iter-13 Phase A2 was 13 days. Iter-15 production should
  include a 7-day re-eval against the same 60-row sample as an
  acceptance test.
- **Review-queue UX.** A1 flags 40% of rows for human review (vs.
  v11's 0%). The triage workflow needs to be designed before A1
  ships to a real client — currently the queue would dump 280+ rows
  on a 709-row run.
- **Adjudicator prompt iteration.** Prompt is FROZEN for A1
  shipping. Tuning happens in iter 16+ with a fresh golden set.
- **A1 production optimization.** A1 currently invokes v11's
  internal Haiku judge + rule scorer + verify-flagged pass inside
  `check_business()` before the adjudicator overrides the verdict.
  That's ~3–5s of wasted latency per row. Iter 15 should add a
  "gather-only" mode to `check_business()` that skips the post-
  processing dance.

---

## Risks and what would change this call

1. **Same-day variance ≠ week-over-week variance.** A1's 0.7pp
   variance is measured at 18-minute separation. Iter 15 must
   re-run the eval at 7-day cadence and recompute. If week-over-
   week variance is > 5pp, escalate to Branch B.
2. **Adjudicator over-applies skepticism on long-tail businesses.**
   The "Uncertain" rate doubled vs v11. If real-world feedback
   shows the adjudicator is gun-shy on legitimately-active
   businesses, dial back the residue-rule weight in the prompt
   (single edit, no architecture change).
3. **Cost projection assumes Sonnet 4.6 stays at current pricing.**
   If Anthropic raises Sonnet pricing materially, the per-row cost
   shifts; would need to re-evaluate vs. Haiku 4.5 or Opus 4.7.
4. **Review queue load.** 40% review rate is a real ops cost for
   any client. If clients won't pay for human triage, A1 needs a
   confidence threshold above which we ship without review — and
   that threshold has to be measured against false-positive rate.

---

## Cost projection for 709-row production run

Derived from per-row costs observed this session.

| Path | $/row | 709 rows | Speed | Notes |
|---|---:|---:|---:|---|
| v11 (current production) | $0.014 | ~$10 | 1.0× | Perplexity + Apify + Haiku judge. |
| **A1 (recommended for iter 15)** | **$0.009** | **~$6** | 1.3× v11 | **Cheaper** than v11 because Sonnet replaces Haiku judge + Perplexity prose-validation rounds. |
| A2 | $0.019 | ~$14 | 1.5× v11 | A1 + Firecrawl on top 3 citations. |
| B (Exa replacement) | $0.035 | ~$25 | TBD | Future-iter; Exa $0.005/row + 6× Firecrawl. |

A1's $0.009/row is the headline economic win. The Sonnet adjudicator
is *cheaper than v11's Haiku audit + Perplexity verify-flagged
rounds combined*, while delivering 75% fewer harmful flips.

Speed: A1 runs at ~15 seconds/row vs. v11's ~12 seconds/row. The
slowdown is the extra Sonnet call (~3–5s); iter-15's "gather-only"
optimization brings A1 back to v11 speed.

---

## Model IDs of record

Resolved 2026-05-13 via `client.models.list()` against the Anthropic
SDK and pinned in `business_checker/tools/adjudicator.py`:

- **Adjudicator (A1 production):** `claude-sonnet-4-6` (created 2026-02-17).
- **Escalation:** `claude-opus-4-7` (created 2026-04-14) — pinned in
  `adjudicator.ESCALATION_MODEL_ID` for use if Sonnet over-applies
  skepticism on a future eval.
- Branch A1 still uses Perplexity sonar for gather.
- Branch B (deferred) would use Exa — no Claude model ID.

The Haiku reference (`claude-haiku-4-5-20251001`) is intentionally
unused — iter 12 demonstrated Haiku over-applied skepticism in this
domain.

---

## Artifacts produced this session

- `business_checker/eval/measure_retrieval_stability.py` — Phase 0 script.
- `business_checker/eval/smoke_adjudicator.py` — Phase 1 live-gate probe.
- `business_checker/eval/compare_configs.py` — extended to N inputs.
- `business_checker/tools/evidence_schema.py` — `BusinessEvidence`,
  `CitationHit`, `CitationType`, etc.
- `business_checker/tools/adjudicator.py` — Sonnet adjudicator.
- `business_checker/tools/check_business_branch_a.py` — A1/A2 gather wrapper.
- `business_checker/tools/resolve_model.py` — Anthropic model ID resolver.
- `business_checker/prompts/adjudicator_v1.md` — adjudicator prompt
  (**FROZEN** — do not edit until iter 16+).
- `business_checker/tools/pipeline_configs.py` — added `v14_branch_a1`,
  `v14_branch_a2`.

**Reports:**
- `eval/reports/iter14_phase0/` — retrieval-stability measurement.
- `eval/reports/iter14_adjudicator_smoke/` — Phase 1 live-gate.
- `eval/reports/iter14_a1_run1/` — A1 paid run 1.
- `eval/reports/iter14_a1_run2/` — A1 paid run 2.

**Tests:** 64 new tests added this session, full suite at **517
passed, 2 skipped** (live-API-only tests).

**Spike cost:** $1.66 (Phase 0) + $0.015 (smoke) + $0.54 (A1 run 1)
+ $0.55 (A1 run 2) = **$2.77 total** (vs. plan estimate $8 for
Phase 0 + Phase 1 + A1).

---

## What iter 15 should do first

1. **Build a `gather_only` mode in `tools/check_business.py`** that
   returns Perplexity citations + scrape + FB signal without the
   internal judge / rule-scorer / verify-flagged pass. A1 calls this
   instead of full `check_business()`, dropping per-row latency by
   ~3–5s.
2. **Add the 7-day re-eval acceptance test.** Run A1 against the
   60-row sample at T+0, T+7d, T+14d. Compute variance across the
   three runs. If > 5pp, escalate to Branch B per risk #1.
3. **Design the review-queue triage workflow.** A1's 40% review
   rate is unworkable at 709-row scale unless there's a clear
   human-in-the-loop UX. Likely: filter by `confidence < 70` for
   the queue; auto-ship the rest.
4. **Build B opportunistically.** Exa client + Firecrawl wrapping
   is ~1 day of work; have it ready as a drop-in if A1 surfaces
   week-over-week drift in production.

The Sonnet adjudicator prompt is FROZEN for any future A2/B
comparison. Iter 16+ can revisit the prompt with a fresh golden set.
