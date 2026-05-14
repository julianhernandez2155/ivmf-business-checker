# STATE.md

## Current Position

Phase: Phase 0 — Foundation
Plan: — (awaiting `/gsd:plan-phase 0`)
Status: Phase 0 context captured + amended for triage routing surface; ready to plan
Last activity: 2026-05-13 — CONTEXT.md amended with D-00-12 (eval-CI emits routing-label distribution alongside decisive accuracy) so Phase 2 doesn't retrofit. Triage decision `.planning/2026-05-13-decision-triage-not-oracle.md` (commit a141951) added to canonical_refs.

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-12)
See: .planning/ROADMAP.md (created 2026-05-12)

**Core value:** Trustworthy bulk verification of veteran/minority-owned business lists with append-only audit history.
**Current focus:** Milestone v1.1 — Web Platform Pivot, Phase 0 (Foundation)

## Progress

Milestone v1.1: 0/7 phases complete

- [ ] Phase 0: Foundation ← **current**
- [ ] Phase 1: Cache-Only Verification
- [ ] Phase 2: Live Verification
- [ ] Phase 3: Manual Workflows
- [ ] Phase 4: Outreach (externally blocked by IT — Resend DNS)
- [ ] Phase 5: Analytics & Receipts
- [ ] Phase 6: Decommission Desktop

## Accumulated Context

**v1.0 (desktop) is feature-complete and frozen.** All verification logic in `business_checker/tools/` (check_business, scrape_website, cache, checkpoint, build_output, columns) is preserved and ported as-is into the Railway worker. The Tkinter GUI and `run_checker.py` are not maintained going forward.

**Eval gold set lives at `business_checker/eval/`** and must run in CI on every worker deploy with a regression gate.

**Reference Run folders kept:** `business_checker/Runs/BMOSG_All_Businesses_2026-04-30_1619/` and `business_checker/Runs/Alabama_Product_Based_VOBs_2026-04-07_131659_7288/` — used as regression baselines (Phase 6 acceptance).

**Repo cleanup completed 2026-05-12:** 22 MB → 8.2 MB. Removed stale runs, .DS_Store, __pycache__, .pytest_cache, .superpowers, and a duplicate `Business Checker/.env` that contained a real Perplexity key. **Perplexity key rotation recommended.**

**Architecture locked-in (see PROJECT.md Key Decisions):**
- Next.js on Vercel (UI + auth + lightweight API)
- Supabase (Postgres + Auth + Realtime + pgmq + Storage)
- Railway (Python FastAPI worker pulling pgmq, runs existing check_business.py)
- Resend (transactional email on IVMF subdomain)

## Phase 0 Preconditions

Before opening `/gsd:plan-phase 0`:

1. **Aggregator extraction (v1.0 polish):** Multi-pass aggregator extracted to `business_checker/tools/aggregator.py`. Eval gold set re-validates unchanged. This is NOT a Phase 0 deliverable; it is a Phase 0 dependency.
2. **Supabase project provisioned** (empty schema acceptable).
3. **Railway project provisioned** for the Python worker (no deploy yet).
4. **Resend DNS ticket filed with IT** for IVMF subdomain (Phase 4 path-critical; file at Phase 0 entry, IT does the slow work in parallel).

## Open Externally-Blocked Items

- **IVMF subdomain + Resend DNS records** (SPF/DKIM/DMARC) — IT ticket (gates Phase 4 only). File at Phase 0 entry.
- **Hosting residency confirmation** — Jim/IT (informational, non-blocking).
- **Data retention policy for raw provider response bodies** — Jim (default: 30d to match v1.0).

## Key Decisions Carried Forward

- Phase 1 stays separate as cache-only (no API calls); Phase 2 adds live verification.
- Aggregator extracted as v1.0 polish BEFORE Phase 0 begins.
- PII compliance is NOT a phase gate; datasets are public registries. Upload-parse allowlist remains as defense-in-depth.
- Eval-CI gate green by Phase 0 exit (even though aggregator doesn't land in worker until Phase 2).
- Two pgmq queues: `q_verify` and `q_aggregator` (separate vt + payload).
- `business_current_state` is trigger-maintained, NOT a materialized view.

## Session Continuity

Next action: `/gsd:plan-phase 0` to decompose Foundation into executable plans.

---
*Last updated: 2026-05-12 — roadmap created, Phase 0 current focus*
