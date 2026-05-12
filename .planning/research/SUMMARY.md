# Project Research Summary

**Project:** IVMF Business Checker — Milestone v1.1 (Web Platform Pivot)
**Domain:** Hosted bulk business-verification SaaS with append-only audit + outreach
**Researched:** 2026-05-12
**Confidence:** HIGH

## Executive Summary

v1.1 wraps the preserved v1.0 Python verification engine (Perplexity Sonar + FireCrawl + multi-pass aggregator + eval gold set, ~2,000 LOC at `business_checker/tools/`) inside a Vercel/Next.js frontend backed by Supabase (Postgres + Auth + Realtime + pgmq + Storage) and a Railway Python FastAPI worker. The verification engine itself is treated as a **library** the worker imports unchanged; everything new is in the multi-tenant data, queue, auth, manual workflows, and outreach surfaces wrapped around it. Architecture is essentially Middesk-shaped (KYB + audit ledger + review queue) plus IVMF-specific eval-as-CI-gate and outbound email verification.

The keystone is an **append-only `verifications` ledger** with idempotency keys, fronted by canonical business identity (EIN auto-merge, 2-of-N → admin queue), feeding a trigger-maintained `business_current_state` table. Every later feature (cache, aggregator, audit, review, outreach, analytics, drift detection) reads or writes through that ledger. Get the schema, RLS, idempotency, and codegen pipeline right in Phase 0; the rest of the milestone composes cleanly.

Top risks are all preventable but compound if deferred: double-billing from misplaced retry logic, silent canonical merges (registered-agent collisions), Realtime reconnect storms, Pydantic/Postgres schema drift, and PII boundary violations once outreach ships. The outreach phase is externally blocked (IT for Resend DNS, Jim for PII signoff) and must be scheduled last.

## Stack Additions (roadmap-relevant only)

- **Next.js 16.2 + React 19 + Tailwind 4** on Vercel — App Router server actions.
- **Supabase Postgres 17** with `pgmq` (durable queue), `pg_trgm` + `fuzzystrmatch` (canonical match), `pg_cron` (heartbeat watchdog + weekly eval), `pgcrypto` (HMAC outreach tokens).
- **Drizzle 0.45 (TS)** + **datamodel-code-generator 0.57 (Python)** — both introspect live Postgres → typed models in both languages. Supabase CLI owns RLS/triggers/cron.
- **Railway** for the Python worker (FastAPI 0.136 + psycopg 3.3 + tembo-pgmq-python 0.10 + tenacity 9.1 + usaddress 0.5.16).
- **Resend 6.12** + react-email — transactional + outreach on an IVMF subdomain.
- **Preserved v1.0:** check_business.py, scrape_website.py, columns.py, build_output.py, aggregator override logic, eval harness/gold set, pydantic 2.12, pandas 2.2.
- **Rejected:** Supabase Edge Functions / Vercel serverless for verification (timeout caps); `@supabase/auth-helpers-nextjs`; psycopg2; supabase-py for worker DB queries; `getSession()` in Server Components.

## Feature Table Stakes (P1, grouped)

- **auth:** TS-1 magic-link + password (domain allowlisted); TS-2 two-role RBAC in middleware **and** RLS (via `app_metadata`).
- **canonical-matching:** TS-11 EIN auto-merge; TS-12 2-of-N → `review_queue` (never auto-merge); D-1 append-only `verifications` with idempotency keys; D-14 per-row provenance.
- **jobs:** TS-3 CSV/XLSX upload + column mapping; TS-4 pre-flight cost estimate; TS-5 batched Realtime progress; TS-6 resumable jobs (pgmq + heartbeat + idempotency); TS-7 run history; TS-13 admin-managed API keys + hard budget cap; TS-15 error log + retry-failed-rows.
- **manual-workflows:** TS-14 unified review queue (2-of-N + uncertain + outreach responses); TS-16 admin edits write new `verifications` rows (never UPDATE).
- **outreach (Phase 5, externally blocked):** D-6 admin-approved outreach tickets; D-7 HMAC-tokenized response form with admin approval gate before verification write.
- **analytics:** D-3 eval harness in CI as deploy gate; D-9 cache-hit trending; D-10 spend dashboard; D-11 status distribution.
- **export:** TS-8 XLSX export byte-compatible with v1.0 columns (reuses `build_output.py`); TS-9 run-completion email; TS-10 shared canonical cache (the entire pivot ROI).

## Differentiators worth committing to in v1.1

1. **D-1 Append-only ledger + idempotency keys** — the moat against silent corruption; every audit/analytics/aggregator feature falls out for free.
2. **D-3 Eval harness in CI as deploy gate** — addresses Pitfall 8; protects aggregator from silent prompt rot; competitors don't expose it.
3. **D-17 Reupload dedupe demo** — the visible "uploaded 50k, only 12k need API calls" moment; pitch artifact for Jim/IVMF leadership.
4. **D-5 Random-sample labeling UI** — grows the gold set from production; feeds D-4 weekly drift alert.
5. **D-15 + D-18 Pause/resume + idempotent run resumption** — the "browser-close-safe / credit-exhaustion-safe" story that justified the pivot.

## Anti-features to explicitly reject

| Trap | Failure mode |
|------|--------------|
| AF-1 Auto-merge any 2-of-N (no EIN) | Registered-agent / holding-co / answering-service collisions silently corrupt canonical DB; eval scores rise falsely. |
| AF-2 Auto-accept outreach form responses | Token URLs leak via email forwards; scrapers/competitors submit; verifications corrupted. |
| AF-5 Soft-delete on `verifications` | Breaks append-only audit guarantee; IVMF can't prove what was claimed when. |
| AF-8 Infinite auto-retry with backoff | FireCrawl 429 / Perplexity outages burn entire monthly cap in retry storm. |
| AF-9 Auto-extend budget cap on hit | Defeats the cap; turns a $250 surprise into $2,500. Hard pause + admin email. |
| AF-12 Per-user custom prompts | Eval harness covers ONE prompt; user edits silently bypass regression gate. |

## Architecture at a glance

```
        ┌──────── Users (admin / analyst) ────────┐
                            │ HTTPS
                            ▼
┌─────────────────────────────────────────────────┐
│ VERCEL — Next.js 16 App Router            [NEW] │
│  /runs  /review  /outreach  /analytics          │
│  /api/upload (signed-URL)  /api/outreach/respond│
└──────┬─────────────────────────────────┬────────┘
   anon │ supabase-js + Realtime WS      │ Resend SDK
service │ (server-only)                  │
        ▼                                 ▼
┌─────────────────────────────────┐  ┌───────────────────┐
│ SUPABASE  (Postgres 17)   [NEW] │  │ RESEND      [NEW] │
│ pgmq · pg_trgm · pg_cron        │  │ IVMF subdomain    │
│ pgcrypto · Auth + RLS           │  │ SPF/DKIM/DMARC    │
│ Tables: businesses ·            │  │ Inbound webhook ──┼──┐
│   verifications (append-only) · │  └───────────────────┘  │
│   business_current_state ·      │                         │
│   runs · run_rows · review_q ·  │                         │
│   outreach_tickets/responses ·  │                         │
│   api_keys · budget_ledger ·    │                         │
│   audit_log                     │                         │
│ Storage: uploads / exports      │                         │
└─────────┬───────────────────────┘                         │
          │ pgmq long-poll + INSERTs                        │
          ▼                                                 │
┌─────────────────────────────────────────────────────────┐ │
│ RAILWAY — Python 3.12 FastAPI worker              [NEW] │ │
│  dispatcher · heartbeat · verify_row · aggregator ·     │ │
│  outreach_send · outreach_response ◄────────────────────┘ │
│  eval_run · realtime_batcher · budget_guard ·             │
│  canonical (EIN + 2-of-N) · idempotency                   │
│                                                           │
│  business_checker/tools/                    [REUSED v1.0] │
│   check_business.py · scrape_website.py · columns.py ·    │
│   build_output.py · aggregator override · eval gold set   │
│  [REMOVED]: cache.py · checkpoint.py · run_checker.py ·   │
│             business_checker_gui.py                       │
└────┬──────────────────────────────┬───────────────────────┘
     ▼                              ▼
 Perplexity Sonar              FireCrawl
```

## Build order with phase-entry gates

| Phase | Goal | Entry Gates | Pitfalls Addressed | Externally Blocked? |
|-------|------|-------------|--------------------|--------------------|
| **0 Foundation** | Schema + RLS + auth + worker scaffold + eval-CI green; no business logic | None | P4 schema codegen, P7 cap schema, P10 PII allowlist, P11 pgmq vt config, P12 Realtime RLS scaffolding, P1 idempotency schema | N |
| **1 Cache-only** | CSV upload → canonical match → cache or "not yet verified" → XLSX export. Zero API calls. | Phase 0 schema + codegen-in-CI passing; eval-CI gate active | P5 canonical silent-merge (EIN-only auto; 2-of-N queue; collision blocklist) | N |
| **2 Live verification** | End-to-end real API run; multi-pass aggregator → `business_current_state`; pause/resume on credit exhaustion | Phase 1 canonical + cache + export proven; admin keys + budget cap landed; aggregator extracted to `tools/aggregator.py` | P1 double-billing, P2 Realtime storms, P6 phantom reads, P7 provider-truth reconciliation, P8 eval gold-set count assertion, P11 heartbeat + SIGTERM drain | N (Jim PII signoff strongly recommended; see Q3) |
| **3 Manual workflows** | Unified review queue, random-sample labeling, admin "edits" write new rows | Phase 2 producing real merge_review/uncertain rows; UPDATE/DELETE triggers on `verifications` shipped | P9 run immutability (BEFORE UPDATE triggers) | N |
| **4 Outreach** | Admin-approved tickets → Resend → tokenized form → admin approval → verification | IVMF subdomain DNS verified in Resend; Jim PII signoff recorded as artifact | P3 anon outreach RLS (service-role + HMAC), P10 PII boundary final gate | **Y — IT + Jim** |
| **5 Analytics + receipts** | Dashboard (cache, $, status, outreach funnel), weekly drift cron, completion receipts | Phase 4 producing outreach data; eval harness already in CI | Weekly drift closes loop on P8 | N |
| **6 Decommission desktop** | Regression vs BMSG + Alabama VOB; tag v1.1.0; archive v1.0 | All prior phases shipped; eval baseline matched | — | N |

Ordering rationale: **schema before features**, **cache before live API** (bounded cost during integration testing), **live before review** (review queue needs real low-confidence rows), **outreach last** (only externally-blocked phase).

## Watch Out For (top 8)

1. **Double-billing on retries (P1)** — idempotency key on **API call**, not just DB row; `INSERT … ON CONFLICT DO NOTHING` on `api_calls` dedup table *before* spending money.
2. **Realtime reconnect storms (P2)** — never per-row; batch via single `run_progress` row updated every 2s.
3. **Schema/Pydantic drift (P4)** — `datamodel-code-generator` in CI; `git diff --exit-code` fails build; Pydantic `extra='forbid'`.
4. **Canonical silent merge (P5)** — EIN-only auto-merge; blocklist for registered-agent addresses, `*.wixsite.com`, answering-service phones; nightly merge re-validation.
5. **Aggregator phantom reads (P6)** — `passes_completed` counter on `run_rows`; aggregator fires only on `passes_completed = passes_required`; `SELECT … FOR UPDATE` on projection.
6. **Cost cap drift (P7)** — pre-flight estimate **and** live tally from provider response headers; daily reconciliation against provider billing; 80%/100% soft/hard caps.
7. **Run immutability violated by admin (P9)** — `BEFORE UPDATE` trigger raises; admin edit = INSERT new row with `source='admin_edit'`.
8. **PII leak to external API (P10)** — explicit allowlist (`business_name`, `city`, `state`, `naics`, `website`); pre-flight regex PII scan on upload; `api_calls.payload_redacted` audit row per outbound request.

## Open Questions for Julian

**Phase-shape questions (block roadmap):**

1. **Phase 1 cache-only demoability:** Phase 1 ships a working web app that **cannot call any external API**. Demoable to Jim, or fold Phases 1+2 into one "live verification" phase? Trade-off: combined is harder to land safely; separate gives clean acceptance of schema/canonical/RLS before money is at risk.
2. **Aggregator extraction timing:** Multi-pass lives partly in `run_checker.py` and partly in `check_business.py` (Pattern B). Extract to `business_checker/tools/aggregator.py` as **v1.0 polishing pass before pivot**, or **inside Phase 2**? Earlier = lower per-phase risk; later = avoids touching frozen v1.0.
3. **PII compliance signoff timing:** Uploads contain PII at ingest (owner names + residence on some MWBE rows), not first at Perplexity. Jim's signoff = **Phase 0 precondition** (storage itself is boundary) or **Phase 4 precondition** (outreach is first external leave)? STACK + ARCH lean Phase 4; PITFALLS argues Phase 0 allowlist suffices until then.

**Deferred decisions (downstream code will hardcode):**

4. **Budget cap default value** — starting monthly cap per Perplexity/FireCrawl key. Needs Jim's number.
5. **Outreach response rate kill threshold** — D-12 says "kill if <5%"; needs pilot data.
6. **Raw provider response retention window** — confirm 30 days for `api_calls.payload_redacted` (matches v1.0 SQLite cache TTL)?
7. **pgmq `set_vt` heartbeat stability** — Phase 0 spike needed; `tembo-pgmq-python@0.10.0` claims support but unexercised under our multi-hour real loads.
8. **Provider-truth API surfaces** — Pitfall 7 reconciliation depends on Perplexity + FireCrawl per-key spend APIs; existence unverified. If absent, live-tally cap is the only defense. Verify during Phase 2.

## Roadmap Implications (must not miss)

- **Phase 0 carries disproportionate weight.** It MUST include: `idempotency_key UNIQUE` on `verifications`, Pydantic/Drizzle codegen-in-CI gate, append-only triggers (`BEFORE UPDATE … RAISE EXCEPTION`), audit-log trigger, RLS on `supabase_realtime` publication, allowlist enforcement at upload-parse, pgmq queue config (vt=300s), Resend DNS ticket opened (Phase 4 path-critical). Skip any and they compound across every later phase.
- **Eval CI gate green by Phase 0 exit** even though aggregator doesn't land until Phase 2. Prevents Phase 2 prompt drift from shipping silently.
- **`run_progress` aggregated row, not row-level Realtime** — Phase 2 design constraint with Phase 0 scaffolding. Architectural, not optimization.
- **Two queues, not one:** `q_verify` and `q_aggregator` (separate vt + payload). Worker fan-out is asyncio semaphore per Perplexity tier, not global pool.
- **Outreach has three independent blockers in parallel:** DNS (IT), PII signoff (Jim), HMAC+webhook code. Schedule all three at Phase 4 entry; long-pole is whichever external party moves slowest.
- **`business_current_state` is a trigger-maintained table, NOT a materialized view.** REFRESH blocks readers on 50k-row runs.
- **Decommission desktop (Phase 6) is a real phase** — regression vs `BMOSG_All_Businesses_2026-04-30_1619/` and `Alabama_Product_Based_VOBs_2026-04-07_131659_7288/`, plus Validated-list update.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Versions verified npm/PyPI 2026-05-12; vendor docs verified for `getUser()`, pgmq, Supabase Queues GA. |
| Features | HIGH | Comparables well-documented (Middesk closest); pivot rationale locked in PROJECT.md. |
| Architecture | HIGH | Topology locked in PROJECT.md Key Decisions; this is integration mapping, not greenfield. |
| Pitfalls | HIGH | Informed by v1.0 production + known Supabase/pgmq/Realtime failure modes; stack-specific. |

**Overall:** HIGH

**Gaps:** pgmq long-vt heartbeat stability (Phase 0 spike); provider billing API existence (Phase 2 verify); outreach response rate floor (pilot data); compliance signoff scope (Q3 resolution before Phase 0 closes).

## Sources

**Primary (HIGH):** npm + PyPI registries (2026-05-12); Supabase docs (Auth, pgmq/Queues GA, Realtime, RLS, Storage); Resend docs (SPF/DKIM/DMARC, webhook signing); pgmq + tembo-pgmq-python 0.10 release notes; Pydantic v2 + datamodel-code-generator docs; v1.0 codebase; PROJECT.md + STATE.md (2026-05-12).

**Secondary (MEDIUM):** Middesk / Clearbit / ZoomInfo / Apollo.io / NeverBounce product docs; internal memory `enterprise_ai_standards_ref.md`.

**Tertiary (LOW — flagged):** Perplexity + FireCrawl per-key spend APIs (existence unverified); pgmq `set_vt` under sustained multi-hour load at our scale.
