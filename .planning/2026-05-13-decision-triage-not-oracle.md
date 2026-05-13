# Decision: AI Triages Verification Work, It Doesn't Decide Status

**Date:** 2026-05-13
**Status:** Locked
**Supersedes:** None (clarifies framing implicit in v1.1 ROADMAP Phase 2)

## TL;DR

The Business Checker is **not** a status oracle. It is a **triage engine** that classifies rows into routing buckets so humans can resolve verification work at scale. Final status writes come from staff actions and owner responses, not from the AI.

This decision does **not** change the v1.1 roadmap phases. It locks the *conceptual frame* and the *Phase 2 output schema* so that downstream phases (Manual Workflows, Outreach, Analytics) compose cleanly.

## Why This Frame

Iter 14 spike (2026-05-13, see `business_checker/docs/2026-05-13-iter14-decision.md`) measured the ceiling of "AI decides status alone":

| Pipeline | Decisive accuracy | Harmful flips / 60 | Review queue |
|---|---:|---:|---:|
| v11 baseline | 66.0% | 8 | n/a |
| A1 (Sonnet adjudicator on Perplexity gather) | 65.6% (avg of two runs) | 2 | 24/60 (~40%) |

Reading those numbers as "the model is wrong 34% of the time" misses the point. Sonnet-as-adjudicator is **honest about uncertainty** — it surfaces 40% of rows for review instead of forcing a decisive call. That's a feature, not a failure, *if* the surrounding product treats those rows as triaged work, not unresolved AI errors.

The Codex reframe (2026-05-13) makes this explicit: the value the AI delivers is **work routing at scale**, not status accuracy. A human reviewing 24 ambiguous rows is the system working correctly. A human reviewing 60 rows because we didn't trust the AI's "active" verdicts would be the system failing.

## What Phase 2 Outputs (the routing schema)

Phase 2 must emit one of these routing labels per row, derived from `(verdict, confidence, requires_review, contact_available)`:

| Routing label | Mapping rule |
|---|---|
| `Active - auto accepted` | `verdict=Active` AND `confidence >= 70` AND `requires_review=False` |
| `Likely Closed - strong evidence` | `verdict=Likely Closed` AND `confidence >= 70` AND `requires_review=False` |
| `Uncertain - manual review recommended` | `requires_review=True` AND `contact_available=False` |
| `Uncertain - outreach recommended` | `requires_review=True` AND `contact_available=True` |
| `Likely Closed - outreach recommended` | `verdict=Likely Closed` AND `confidence < 70` AND `contact_available=True` |
| `No contact available` | `verdict=Uncertain` AND `contact_available=False` (terminal — Phase 3 picks up) |

The exact thresholds may move with Iter 16 prompt tuning; the **shape of the schema** is locked.

This mapping is a Phase 2 implementation task (downstream of `check_business_branch_a` in the worker), **not** a prompt rewrite. Adjudicator prompt at `business_checker/prompts/adjudicator_v1.md` stays FROZEN.

## Phase Responsibilities (sharpened)

| Phase | Responsibility | Does NOT do |
|---|---|---|
| **Phase 2: Live Verification** | Run gather + adjudicate + emit routing label + write `business_current_state` | Force manual review, send emails, write final status |
| **Phase 3: Manual Workflows** | Staff resolve `Uncertain - manual review` rows, override status, label samples | Send outreach (that's Phase 4) |
| **Phase 4: Outreach** | Send tokenized forms to `*outreach recommended` rows; start 30-day clock; admin approves responses | Auto-write status from form responses without admin approval |
| **Phase 5: Analytics** | Prove the queue is clearing: auto-accepted count, review resolution rate, response rate, 30-day nonresponse aging | Make any verification decisions |

## The 30-Day Nonresponse Rule (Phase 4)

After Phase 4 outreach with no response within 30 days, the row transitions:

`Uncertain - Awaiting Verification` → `Likely Closed - No Response`

This is **not** the same as `Likely Closed - strong evidence`. The Analytics phase must distinguish:

- `Likely Closed - by evidence` (AI + adjudicator)
- `Likely Closed - by no response` (silence after outreach)

Both remove the row from active confidence; only the first carries evidentiary weight.

## What Stays Locked

1. **Adjudicator prompt is frozen** — `business_checker/prompts/adjudicator_v1.md`. Tuning is Iter 16, after week-over-week drift data exists.
2. **A1 pipeline is the production gather** — Sonnet adjudicator on v11 retrieval. Branch B (Exa + Firecrawl) remains fallback-only.
3. **Iter 14 baseline is the measurement gate** — `v11_fresh 2026-05-13: 66.0% / 8 harmful` and `A1: 65.6% / 2 harmful`. Do not invalidate this comparison surface by changing the model or prompt before Iter 15 production wiring lands.
4. **Iter 14 spike acceptance test** — still required: run A1 on the v1 60-row sample at T+0, T+7d, T+14d. Drift >5pp escalates to Branch B.

## What Changes (Phase 2 plan tasks)

When Phase 2 planning begins, the plan must include:

- [ ] Routing-label mapping function in worker (post-adjudicator)
- [ ] Storage schema: `verifications.routing_label` (enum, 6 values above)
- [ ] Phase 2 acceptance test: routing label distribution on BMSG matches expected ratios (≤5% in any "uncertain" bucket without contact)
- [ ] No emails sent from Phase 2 (verified by mocking Resend in test env)

## Open Questions (deferred to Phase 2 plan)

- Exact confidence threshold for `auto accepted` (70 is a placeholder; calibrate against gold-set during Phase 2 planning)
- Whether `requires_review=True` AND `confidence >= 70` is even reachable from the current adjudicator (probably not; verify against Iter 14 predictions before encoding the rule)
- UX for staff in Phase 3 to **disagree with the routing** (e.g., move `auto accepted` row to review queue) — likely a queue filter + manual override

## References

- `business_checker/docs/2026-05-13-iter14-decision.md` — Iter 14 measurement memo
- `business_checker/docs/2026-05-13-iter14-search-vs-reasoning-spike.md` — Iter 14 spike plan
- `.planning/ROADMAP.md` — v1.1 phase definitions
- `.planning/REQUIREMENTS.md` — 50 v1.1 requirements (routing schema may add 1–2 new MANUAL-* / ANALYTICS-* entries)
