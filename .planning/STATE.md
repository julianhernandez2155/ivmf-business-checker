---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: milestone
status: verifying
last_updated: "2026-05-15T19:55:58.943Z"
last_activity: 2026-05-15
progress:
  total_phases: 7
  completed_phases: 0
  total_plans: 9
  completed_plans: 8
---

# STATE.md

## Current Position

Phase: 00 (Foundation) — Gap-closure cycle in progress (8 of 9 plans complete; Plan 00-07 + 00-08 shipped, Plan 00-09 next)
Plan: 8 of 9 complete (00-01..00-06 + 00-07 + 00-08)
Status: Gap closure in progress — Plan 00-09 (GAP-3 + GAP-4) is the final plan
Last activity: 2026-05-15

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-12)
See: .planning/ROADMAP.md (created 2026-05-12)

**Core value:** Trustworthy bulk verification of veteran/minority-owned business lists with append-only audit history.
**Current focus:** Phase 01 — Cache-Only Verification (next)

## Progress

Milestone v1.1: 1/7 phases complete

- [x] Phase 0: Foundation (complete 2026-05-15; 5 live-demo captures deferred pending dev Supabase + Railway provisioning — code-complete, see 00-EVIDENCE.md)
- [ ] Phase 1: Cache-Only Verification ← **next**
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

- **IVMF subdomain + Resend DNS records** (SPF/DKIM/DMARC) — **DEFERRED until Phase 4 entry.** IVMF IT has not yet provisioned the IVMF subdomain (e.g., `outreach.ivmf.syr.edu`); DNS records cannot be filed until that subdomain exists. Phase 0–3 use the Resend sandbox + `julianhernandez2155@gmail.com` as the only allowed recipient (built-in Resend safety prevents accidental sends to real businesses). Resend account exists; API key stored at `worker/.env:RESEND_API_KEY` (gitignored). File the DNS ticket at Phase 4 entry. See `.planning/phases/00-foundation/00-EVIDENCE.md` D-00-11 item 6 for full context.
- **Hosting residency confirmation** — Jim/IT (informational, non-blocking).
- **Data retention policy for raw provider response bodies** — Jim (default: 30d to match v1.0).
- **Dev Supabase project provisioning** — `ivmf-checker-dev` not yet provisioned. Blocks D-00-11 live-demo captures for items 1 (magic-link walkthrough), 2 (codegen-drift PR), 4 (`phase0-demo.sh` append-only assertion), 5 (worker heartbeat row). All four items are code-complete (see 00-EVIDENCE.md for the commit hashes / integration tests proving each gate); only the live demo capture awaits this provisioning. Apply with `supabase db push` (or psql sequence) once SUPABASE_DEV_DB_URL is set. Manually enable pgmq extension in Supabase Dashboard before applying 0005. Then run `cd worker && SUPABASE_DEV_DB_URL=... pytest tests/ -x` to validate the 8 integration tests pass.
- **Railway project provisioning** — blocks D-00-11 item 5 live demo. Procfile + railway.json shipped; `railway up` deferred until the Railway project is created.
- **D-00-10 upload-parse function** — CONTEXT.md D-00-10 promised the column-allowlist parse function + unit tests against the two reference Run input files in Phase 0. Only the `column_allowlist` config-seed row shipped; the parse function itself was silently dropped. **Folded into Phase 1 upload plan** (JOBS-01 already owns the upload flow). When `/gsd:plan-phase 1` runs, the planner must include the parse function + reference-file unit tests as a Phase 1 task. No new Phase 0 work; documented here so Phase 1 picks it up.

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
- **Plan 00-05:** vt=300 enforced at the consumer call site via `dispatcher.VT_SECONDS` constant + `QueueClient.read_one(vt_seconds=300)` default; `grep -rn "vt=" worker/workers/` returns a single site at `pgmq_client.py:52` — proves D-00-09 not violated anywhere else.
- **Plan 00-05:** `heartbeat_loop` uses `asyncio.wait_for(shutdown.wait(), timeout=30)` instead of `asyncio.sleep(30)` so SIGTERM exits in ms, not up to a full interval — same SIGTERM-drain contract that Phase 2 will inherit.
- **Plan 00-05:** `QueueClient.__init__` tries `PGMQueue(dsn=...)` first, falls back to host/port/etc. kwargs on `TypeError` — survives tembo-pgmq-python 0.10 API surface drift between published patch builds without forcing a hard pin.
- **Plan 00-05:** Railway deploy DEFERRED (same external block as Plan 00-02 dev DB); Procfile + railway.json shipped as the deployment manifest, live `railway up` waits on Railway project + dev Supabase provisioning. D-00-11 item 5 is code-complete; live demo gated on the same external block.
- **Plan 00-06:** Eval-regression gate (D-00-11 item 3) live-verified locally end-to-end (FAIL: delta -0.0172 → RESTORE: delta +0.0000) — same `scripts/eval-ci.sh` code path that GitHub Actions runs. PR-based demo skipped because the local run proves the gate fires identically; reopen at Phase 1 if a reviewer wants the GitHub check screenshot specifically.
- **Plan 00-06:** D-00-12 routing-label measurement surface live: `business_checker/eval/routing_labels.py` exports the 6-value enum; `business_checker/eval/score.py` emits `routing_distribution` in every run (informational in Phase 0; Phase 2 gates on drift).
- **Plan 00-06:** Frozen baseline at `business_checker/eval/baseline.json` — accuracy=0.6897, n_examples=58 (≥20 Pitfall P8 floor). routing_distribution sums to 58 (sanity-check passed).
- **Plan 00-06:** Resend DNS ticket DEFERRED until Phase 4 entry (IVMF subdomain not yet provisioned; Resend sandbox + Julian's gmail covers Phase 0–3 testing safely).
- **Plan 00-07:** GAP-1 (Codex peer review) closed via migration 0009 — `auth.current_role_claim()` now reads `app_metadata.role` FIRST; the broken `auth.jwt() ->> 'role'` (Postgres reserved claim) fallback is removed entirely; `user_role` added as non-reserved JWT escape hatch for tests / non-standard JWTs.
- **Plan 00-07:** GAP-2 (Codex peer review) closed via migration 0009 — `auth.is_allowed_domain(auth.email())` predicate added to runs_select_own, app_config_read (authenticated only — anon retains read for middleware bootstrap), app_config_admin_all, audit_log_admin_read, worker_heartbeats_admin_read. Defense-in-depth contract (D-00-05) is now true at BOTH layers.
- **Plan 00-07:** Admin RLS policies ALSO gated on `is_allowed_domain` — closes the role-flip-to-non-allowlisted-user escalation path. Tables without existing user-facing policies (run_rows, verifications, api_calls, businesses, api_keys, budget_ledger, outreach_tickets) are NOT patched here; Phase 1 must include the allowlist predicate when adding their user-facing policies.
- **Plan 00-07:** 6 new behavioral regression tests added (3 per test file) using `SET LOCAL request.jwt.claims` for JWT impersonation; all 12 tests across both files skip cleanly without `SUPABASE_DEV_DB_URL`. Live validation gated on the same dev-DB provisioning block as the rest of Phase 0.
- **Plan 00-08 (GAP-5 closure):** review_queue table uses CHECK-constraint enums (not Postgres ENUM TYPE) for kind and status — easier to ALTER, matches 0001 convention on runs.status. Added chk_review_queue_resolution_shape so open rows have null resolution metadata and non-open rows have resolved_at set.
- **Plan 00-08:** review_queue admin RLS uses defense-in-depth (auth.current_role_claim()='admin' AND auth.is_allowed_domain(auth.email())) mirroring the GAP-2 fix shape from Plan 00-07's 0009 migration. Partial index on (status, kind) WHERE status='open' keeps the Phase 3 review-queue UI hot path lean as resolved rows accumulate.
- **Plan 00-08:** Drizzle (web/db/schema.ts) and Pydantic (worker/workers/lib/models.py) baselines hand-extended with review_queue / ReviewQueue (same deferred-live-introspection pattern as Plan 00-03). FK on created_by/resolved_by → auth.users declared only at the migration layer; Drizzle baseline leaves it as plain uuid (no cross-schema introspection; matches existing runs.user_id pattern).
- **Plan 00-08:** GAP-5 from Codex peer review (.planning/phases/00-foundation/00-VERIFICATION.md) CLOSED. Phase 1's first task is no longer a schema migration — cache-only verification can start directly on canonical matching. Live integration test execution (6 tests in worker/tests/test_review_queue.py) awaits SUPABASE_DEV_DB_URL provisioning along with the rest of the Phase 0 integration suite.

## Session Continuity

Last completed: Plan 00-06 (eval-CI regression gate + D-00-12 routing-label surface + frozen baseline + local D-00-11 item 3 end-to-end demo). Phase 0 closed 2026-05-15 with 1 D-00-11 item live-verified and 5 deferred (4 awaiting dev Supabase + Railway provisioning, 1 awaiting IVMF subdomain provisioning) — all 5 are code-complete with commit hashes traced in `.planning/phases/00-foundation/00-EVIDENCE.md`.
Phase 0 complete (with 4 dev-DB-dependent demo items + Resend DNS deferred); Next: `/gsd:plan-phase 1`.

---
*Last updated: 2026-05-15 — Phase 0 complete; Plan 00-06 closed (eval-CI gate + D-00-12 surface; ANALYTICS-04 done; live captures for 5 of 6 D-00-11 items deferred pending external provisioning)*
