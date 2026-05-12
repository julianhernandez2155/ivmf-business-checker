# IVMF Business Checker

## What This Is

An AI-assisted business verification tool used by the Institute for Veterans and Military Families (IVMF) to check whether businesses on uploaded lists (BMSG, MWBE, VOB datasets, 500–50,000+ rows) are still operating. Currently a Python desktop application (Tkinter GUI + headless runner) that calls Perplexity Sonar + FireCrawl per business and classifies as active, likely closed, closed, or uncertain.

## Core Value

**Trustworthy bulk verification of veteran/minority-owned business lists with append-only audit history.** Outputs are used by IVMF staff and downstream stakeholders to act on real businesses — accuracy and traceability are non-negotiable.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

- ✓ Single-business verification via Perplexity Sonar API — v1.0
- ✓ Concurrent batch runner with configurable QPS (1/3/8 workers per Perplexity tier) — v1.0
- ✓ Run-as-first-class-entity (each upload = a timestamped folder under `Runs/`) — v1.0
- ✓ Thread-safe CSV checkpoint with resume after crash — v1.0
- ✓ Retry-failed-rows workflow (`rewrite_checkpoint`) — v1.0
- ✓ Multi-pass aggregator with override logic — v1.0
- ✓ SQLite cache keyed by normalized (name, city, state) with 30-day TTL — v1.0
- ✓ Excel output assembly with appended AI columns (`tools/build_output.py`) — v1.0
- ✓ Eval harness against labeled gold set — v1.0
- ✓ Tkinter GUI + headless `run_checker.py` modes — v1.0
- ✓ Website scraping fallback for low-signal businesses — v1.0

### Active

<!-- Current scope. Building toward these (Milestone v1.1). -->

- [ ] Web platform on Supabase + Next.js + Railway Python worker
- [ ] Shared verification database (cache layer across all uploads and users)
- [ ] Admin/user auth with two-role RBAC
- [ ] Admin-managed Perplexity/FireCrawl API keys with monthly budget caps
- [ ] Canonical business matching (EIN auto-merge or 2-of-N field consensus)
- [ ] Append-only verifications ledger with idempotency keys
- [ ] Durable background jobs that survive browser close / crash / credit exhaustion
- [ ] Manual random-sample labeling UI
- [ ] Email outreach via Resend (admin-approved, tokenized form responses)
- [ ] Analytics dashboard
- [ ] CSV/XLSX export with appended AI columns (preserved from desktop)
- [ ] Run-completion email receipts

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- User-supplied API keys (each user brings own Perplexity key) — Rejected: shifts billing/security burden onto staff, defeats the centralization purpose of the pivot. Admin-managed keys instead.
- Desktop app (Tkinter GUI) continued maintenance — Frozen at v1.0. Web platform replaces it; Python verification engine code is reused on the worker.
- Auto-merge of non-EIN canonical matches — Rejected: shared addresses (registered agents), shared domains (holding companies), and shared phones (answering services) make silent merges unsafe. 2-of-N matches route to admin review queue.
- Auto-acceptance of email outreach form responses — Rejected: token URLs can be spoofed; submissions need admin approval before becoming verifications.
- More than two RBAC roles — Out of scope for v1.1. Admin + user only. Re-evaluate if external partners are onboarded.
- Multi-tenant data isolation across IVMF departments — Out of scope for v1.1. RLS scoped by user, not by department.
- On-prem hosting — Out of scope unless IVMF IT mandates. Default is Supabase (AWS us-east) + Railway (US) + Vercel.

## Context

**Technical environment:**
- Existing Python codebase at `business_checker/` (≈2,000 LOC) — verification engine, checkpoint, cache, aggregator, eval harness all live here. **This code is preserved and reused on the worker.**
- ECC harness installed: Supabase MCP, Context7 MCP, OMEGA memory, exa search.
- Julian's stack preferences: Python (backend/worker), TypeScript/Next.js (frontend), Supabase Postgres, Vercel hosting.

**Prior work / what shipped:**
- Phases 1–7 already complete on desktop version: clean repo, restructure, spot-check, eval tool, BMSG run, disagreement analysis, multi-pass aggregator iterations.
- Eval gold set exists at `business_checker/eval/`.
- Two reference Run folders kept post-cleanup (latest BMSG + latest Alabama VOB).

**Pivot rationale (May 2026):**
- Desktop app forced user-supplied API keys — friction for non-technical IVMF staff.
- Each upload re-paid the API for businesses already verified in a prior upload — no cross-user cache.
- Web version enables: shared canonical DB (cost trends toward zero per row over time), admin-managed keys, hours-long resumable jobs, manual verification workflows for uncertain rows, email outreach to confirm operating status from the business directly.

**Stakeholder context:**
- Primary stakeholder at IVMF: Jim Yauger.
- Compliance: PII boundary (owner names + addresses to external APIs) needs Jim/compliance signoff before outreach phase ships.
- IT involvement required for: IVMF subdomain DNS records (Resend SPF/DKIM/DMARC) and any data-residency review.

**Known issues / open from v1.0:**
- SQLite cache key (name+city+state hash) misses common name variants → web version replaces with canonical business model.
- Aggregator override logic depends on full pass history → web version writes pass results to `verifications` and a materialized `business_current_state` table for aggregator reads.

## Constraints

- **Tech stack**: Python (worker, preserved), Next.js (frontend), Supabase (DB/Auth/Realtime/Queue), Railway (long-running worker), Vercel (frontend hosting), Resend (email) — Julian's stack preference + adversarial review concluded this split is necessary because Vercel/Edge/Lambda can't hold hours-long jobs.
- **Resumability**: Every run must survive browser close, worker crash, provider credit exhaustion — Append-only verifications + visibility-timeout pgmq messages + heartbeat watchdog.
- **Auditability**: Runs are immutable after completion; admin "edits" create new verifications, never overwrite — IVMF will be asked to justify status decisions.
- **Cost control**: Pre-flight estimate + per-run cap + monthly cap per API key, with hard stop — A single bad 50k-row upload at $0.005/call = $250.
- **Backward compatibility of outputs**: CSV/XLSX export must remain a drop-in replacement for desktop output — Existing IVMF workflows consume these files downstream.
- **Compliance**: PII to external LLM APIs requires Jim/compliance signoff before outreach phase ships — IVMF policy.
- **Eval discipline**: Eval harness must run in CI on every worker deploy and block on accuracy regression — Override logic and prompt changes will silently rot otherwise.

## Key Decisions

<!-- Decisions that constrain future work. Add throughout project lifecycle. -->

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Pivot from desktop to web | User-supplied API keys created friction; no shared cache across uploads; no resumable hours-long jobs | — Pending (this milestone) |
| Keep Python as the verification engine; deploy worker on Railway | 800 LOC of trusted check_business + aggregator + eval logic; Vercel/Lambda timeouts can't hold hours-long jobs | — Pending |
| Supabase as single source of truth (DB + Auth + Realtime + pgmq + Storage) | Single vendor reduces glue code; native Postgres + pg_trgm + RLS handles canonical matching cleanly | — Pending |
| Append-only `verifications` ledger | Preserves audit history for IVMF; safe re-runs; admin "edits" never destroy data | — Pending |
| Canonical match: EIN auto-merge, 2-of-N → admin review queue | Adversarial review: silent merges on shared addresses/domains/phones corrupt gold set | — Pending |
| Admin-managed API keys with budget caps | Centralizes billing, eliminates per-user key hygiene, enables hard cost stops | — Pending |
| Two-role RBAC (admin + user) for v1.1 | Lowest complexity that meets IVMF staff workflow; deferrable upgrade path | — Pending |
| Idempotency keys on verifications | FireCrawl 429/timeout retries will double-bill and double-write otherwise | — Pending |
| Eval harness blocks worker deploys on regression | Prompt/model changes silently rot the override logic; eval is the only defense | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

## Current Milestone: v1.1 Web Platform Pivot

**Goal:** Replace the Python desktop app with a hosted web platform on Supabase + Next.js + Railway worker that preserves every v1.0 capability while adding shared cache, auth, durable jobs, manual workflows, email outreach, and analytics.

**Target features:**
- Foundation: Supabase project, schema, RLS, Next.js + auth, Railway worker scaffold, pgmq queue, Python models from schema
- Cache-only verification: Canonical matching (EIN + 2-of-N), DB-backed cache, CSV upload → run_rows → verification, CSV/XLSX export
- Live verification: Worker calls existing Python check_business / scrape_website, multi-pass aggregator → business_current_state, Realtime progress (batched), credit-exhaustion pause/resume, eval harness in CI
- Manual workflows: Random-sample labeling UI, manual review queue, admin DB editor with audit log
- Outreach: Admin-approved outreach tickets, Resend on IVMF subdomain, tokenized form responses, admin approval before verification write
- Analytics: Cache hit rate, $ spent vs cap, status distribution, outreach response rate, manual queue depth, weekly eval drift alerts
- Run-completion email receipts

---
*Last updated: 2026-05-12 after milestone v1.1 initialization*
