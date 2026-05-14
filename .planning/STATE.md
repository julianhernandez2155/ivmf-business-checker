---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: milestone
status: executing
last_updated: "2026-05-14T19:59:45.357Z"
last_activity: 2026-05-14
progress:
  total_phases: 7
  completed_phases: 0
  total_plans: 6
  completed_plans: 4
---

# STATE.md

## Current Position

Phase: 00 (Foundation) — EXECUTING
Plan: 5 of 6
Status: Ready to execute
Last activity: 2026-05-14

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-12)
See: .planning/ROADMAP.md (created 2026-05-12)

**Core value:** Trustworthy bulk verification of veteran/minority-owned business lists with append-only audit history.
**Current focus:** Phase 00 — Foundation

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
- **Dev Supabase project provisioning** — `ivmf-checker-dev` not yet provisioned; plan 00-02 migrations + tests written but not applied. Apply with `supabase db push` (or psql sequence) once SUPABASE_DEV_DB_URL is set. Manually enable pgmq extension in Supabase Dashboard before applying 0005. Then run `cd worker && SUPABASE_DEV_DB_URL=... pytest tests/ -x` to validate the 8 integration tests pass.

## Key Decisions Carried Forward

- Phase 1 stays separate as cache-only (no API calls); Phase 2 adds live verification.
- Aggregator extracted as v1.0 polish BEFORE Phase 0 begins.
- PII compliance is NOT a phase gate; datasets are public registries. Upload-parse allowlist remains as defense-in-depth.
- Eval-CI gate green by Phase 0 exit (even though aggregator doesn't land in worker until Phase 2).
- Two pgmq queues: `q_verify` and `q_aggregator` (separate vt + payload).
- `business_current_state` is trigger-maintained, NOT a materialized view.
- **Plan 00-02:** verifications.run_id has ON DELETE CASCADE solely for test fixture cleanup; cleanup uses session_replication_role=replica to bypass BEFORE DELETE trigger.
- **Plan 00-02:** Test fixtures insert deterministic UUID directly into auth.users via service-role (no Supabase admin REST dependency); `_role_guard` fixture catches the pooler-URL footgun.
- **Plan 00-02:** worker_heartbeats lives in 0001 (not 0007) because 0002 RLS references it; 0007 is a placeholder no-op.
- **Plan 00-02:** 0001 migration is non-idempotent by design; convert to `create table if not exists` deferred to Phase 0 polish PR.
- **Plan 00-02:** normalize_name keeps bare "corp" suffix; only "corporation" is stripped (contract-driven).
- **Plan 00-03:** Drizzle schema.ts + Pydantic models.py baselines hand-derived from `0001_init_schema.sql` (dev DB not provisioned); first live `bash scripts/check-drift.sh` either confirms zero-diff or produces a one-time "regenerate baseline" PR.
- **Plan 00-03:** Replaced v1.0 `.github/workflows/ci.yml` (matrix on business_checker) with v1.1 three-job structure (worker-tests, web-tests, worker-integration); v1.0 tests still run inside worker-tests with soft-warn so pre-existing failures don't block.
- **Plan 00-03:** `codegen-drift.yml` runs the D-00-03 hard guard (non-empty `web/drizzle/migrations/` → exit 1) BEFORE any other step, so the gate fires even if other CI steps would have errored.
- **Plan 00-03:** `worker-integration` CI job is gated on `secrets.SUPABASE_DEV_DB_URL != ''` so PRs from fork/no-secret contexts skip cleanly; branch protection should require `worker-tests` + `web-tests` + `codegen-drift`, NOT `worker-integration`.
- **Plan 00-04:** Magic-link only per D-00-04 (no password form). Allowlist defense-in-depth via middleware `getAllowlist()` + RLS `auth.is_allowed_domain()` reading the SAME `app_config.email_domain_allowlist` row.
- **Plan 00-04:** AUTH-03 role storage is `app_metadata.role` only — NO `profiles` table in Phase 0 (Supabase Auth's `app_metadata` is sufficient). `auth.current_role_claim()` RLS helper provides a single canonical read path for both middleware and RLS.
- **Plan 00-04:** Allowlist edge cache TTL = 60s on success, 10s on error, fails CLOSED to `['syr.edu']`. Admin allowlist edits propagate within 60s — acceptable for AUTH-02 since admin edits are rare.
- **Plan 00-04:** `drizzle-kit` pinned to `^0.31` (registry truth on 2026-05-14); STACK.md research baseline `^0.45` conflated drizzle-orm with drizzle-kit version lines.
- **Plan 00-04:** Migration `0008_rbac_role_default.sql` apply to dev DB deferred (no `SUPABASE_DEV_DB_URL`); will land with the rest via `supabase db push` once `ivmf-checker-dev` is provisioned.

## Session Continuity

Last completed: Plan 00-04 (Next.js 16 + Supabase magic-link auth + middleware allowlist + /me page — AUTH-01..03 closed; migration 0008 RBAC + role helper added; 8 vitest tests passing, 7 pytest tests skip cleanly pending dev DB).
Next action: Execute Plan 00-05 (Railway worker + pgmq long-poll + heartbeat — D-00-09, D-00-11 item 5) per ROADMAP.md.

---
*Last updated: 2026-05-14 — Plan 00-04 completed (web auth shell + AUTH-01/02/03; migration apply + live magic-link demo deferred pending dev project provisioning)*
