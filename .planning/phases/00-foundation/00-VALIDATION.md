---
phase: 0
slug: foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-12
updated: 2026-05-12
---

# Phase 0 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (worker/) + vitest (web/) + bash demo script |
| **Config file** | worker/pyproject.toml, web/vitest.config.ts (both installed in Wave 0) |
| **Quick run command** | `cd worker && pytest -x -q && cd ../web && pnpm test --run` |
| **Full suite command** | `make test` (runs worker pytest, web vitest, eval-CI, drift-check) |
| **Estimated runtime** | ~60 seconds (quick) / ~180 seconds (full) |

---

## Sampling Rate

- **After every task commit:** Run quick command for the touched layer (worker or web)
- **After every plan wave:** Run full suite
- **Before `/gsd:verify-work`:** Full suite + `scripts/phase0-demo.sh` must both be green
- **Max feedback latency:** 60 seconds for quick path

---

## Per-Task Verification Map

Per-task map rebuilt from each plan's `requirements:` frontmatter and `<task>` blocks (2026-05-12 revision).
Task IDs follow the convention `{phase}-{plan}-{task}`.

| Task ID | Plan | Wave | Requirement(s) | Test Type | Automated Command | Status |
|---------|------|------|----------------|-----------|-------------------|--------|
| 0-01-* | 01 wave0-test-scaffolding | 0 | (scaffolding) | unit/ci | `cd worker && pytest --co && cd ../web && pnpm test --run --reporter=verbose` | ⬜ pending |
| 0-02-01 | 02 supabase-schema-rls | 1 | CANON-05, CANON-06, CANON-07, CANON-08, AUTH-04 | sql/migration | `psql $SUPABASE_DEV_DB_URL -tAc "select count(*) from information_schema.tables where table_schema='public'"` returns ≥ 11 | ⬜ pending |
| 0-02-02 | 02 supabase-schema-rls | 1 | CANON-05, CANON-06, CANON-07, CANON-08, AUTH-04 | integration | `cd worker && pytest tests/test_schema.py tests/test_append_only.py tests/test_audit_trigger.py tests/test_pgmq.py tests/test_app_config.py tests/test_api_calls.py tests/test_verifications_schema.py tests/test_businesses_schema.py -x` | ⬜ pending |
| 0-02-03 | 02 supabase-schema-rls | 1 | CANON-03 | unit | `cd worker && pytest tests/test_normalize.py -x` | ⬜ pending |
| 0-03-01 | 03 codegen-drift-gate | 2 | (infra — gates CANON-03/CANON-05/CANON-06/CANON-07/CANON-08 from plan 02) | ci | `test -f web/drizzle.config.ts && test -f web/db/schema.ts && grep -q "businesses" web/db/schema.ts` | ⬜ pending |
| 0-03-02 | 03 codegen-drift-gate | 2 | (infra) | ci | `test -f worker/workers/lib/models.py && grep -q "extra.*forbid\\|ConfigDict" worker/workers/lib/models.py` | ⬜ pending |
| 0-03-03 | 03 codegen-drift-gate | 2 | (infra) | ci | `python -c "import yaml; yaml.safe_load(open('.github/workflows/codegen-drift.yml')); yaml.safe_load(open('.github/workflows/ci.yml'))"` | ⬜ pending |
| 0-04-01 | 04 web-auth-shell | 3 | AUTH-01, AUTH-02, AUTH-03 | unit | `cd web && pnpm exec tsc --noEmit` | ⬜ pending |
| 0-04-02 | 04 web-auth-shell | 3 | AUTH-01, AUTH-02, AUTH-03 | integration | `psql $SUPABASE_DEV_DB_URL -tAc "select 1 from pg_proc where proname='current_role_claim' and pronamespace='auth'::regnamespace"` returns 1 | ⬜ pending |
| 0-04-03 | 04 web-auth-shell | 3 | AUTH-01, AUTH-02, AUTH-03 | unit + integration | `cd web && pnpm test --run tests/middleware-allowlist.test.ts tests/auth-magic-link.spec.ts` AND `cd worker && pytest tests/test_rls_domain_allowlist.py tests/test_rbac.py tests/test_allowlist_admin.py -x` | ⬜ pending |
| 0-05-01 | 05 worker-railway-pgmq | 4 | (infra — D-00-09 + D-00-11 item 5) | unit | `python -c "from workers.lib.db import get_pool; from workers.lib.pgmq_client import QueueClient; from workers.lib.shutdown import shutdown"` | ⬜ pending |
| 0-05-02 | 05 worker-railway-pgmq | 4 | (infra) | ci + deploy | `curl https://WORKER_DOMAIN/health` returns 200; psql confirms heartbeat row within 60s | ⬜ pending |
| 0-05-03 | 05 worker-railway-pgmq | 4 | (infra) | unit + integration | `cd worker && pytest tests/test_worker_loop.py tests/test_heartbeat.py -x` | ⬜ pending |
| 0-06-01 | 06 eval-ci-demo | 5 | ANALYTICS-04 | unit | `python -m business_checker.eval.score --gold business_checker/eval/gold.json --out /tmp/test.json && python -c "import json; d=json.load(open('/tmp/test.json')); assert 'accuracy' in d and 'n_examples' in d"` | ⬜ pending |
| 0-06-02 | 06 eval-ci-demo | 5 | ANALYTICS-04 | ci | `python -c "import yaml; yaml.safe_load(open('.github/workflows/eval-ci.yml'))"` | ⬜ pending |
| 0-06-03 | 06 eval-ci-demo | 5 | (D-00-11 item 6) | manual | Resend account created + IT ticket filed; ticket ID recorded in 00-EVIDENCE.md | ⬜ pending |
| 0-06-04 | 06 eval-ci-demo | 5 | (D-00-11 demo) | manual + ci | `bash scripts/phase0-demo.sh` exits 0; both demo PRs (drift + eval) opened, failed CI, closed | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

### Requirement → Plan Coverage

Cross-check that every phase requirement is owned by at least one plan:

| Requirement | Owned by Plan(s) | Verification Task(s) |
|-------------|------------------|----------------------|
| CANON-03 | 02 | 0-02-03 |
| CANON-05 | 02 | 0-02-01, 0-02-02 |
| CANON-06 | 02 | 0-02-01, 0-02-02 |
| CANON-07 | 02 | 0-02-01, 0-02-02 |
| CANON-08 | 02 | 0-02-01, 0-02-02 |
| AUTH-01 | 04 | 0-04-01, 0-04-03 |
| AUTH-02 | 04 | 0-04-01, 0-04-03 |
| AUTH-03 | 04 | 0-04-02, 0-04-03 |
| AUTH-04 | 02 | 0-02-02 |
| ANALYTICS-04 | 06 | 0-06-01, 0-06-02 |

Plans 03 and 05 own no requirements directly — they are infrastructure (codegen-drift gate
and Railway worker scaffold). They GATE requirements owned by other plans (e.g. plan 03's
drift workflow protects the schema artifacts that satisfy CANON-05/06/07/08 from plan 02).
This is intentional and consistent with the phase architecture.

---

## Wave 0 Requirements

- [ ] `worker/pyproject.toml` — add pytest 8.x + pytest-postgresql + psycopg[binary] dev deps
- [ ] `worker/tests/conftest.py` — shared fixtures (db connection, test schema bootstrap)
- [ ] `worker/tests/test_schema.py` — stub asserts tables exist for CANON-05
- [ ] `worker/tests/test_append_only.py` — stub for CANON-06 (UPDATE/DELETE raises, UNIQUE rejects dup)
- [ ] `worker/tests/test_audit_trigger.py` — stub for CANON-07 (audit_log row + jsonb diff)
- [ ] `worker/tests/test_pgmq.py` — stub for CANON-08 (q_verify, q_aggregator exist with vt=300)
- [ ] `worker/tests/test_rls_domain_allowlist.py` — stub for AUTH-03 (RLS blocks non-allowlisted JWT)
- [ ] `worker/tests/test_allowlist_admin.py` — stub for AUTH-04 (admin row edit extends allowlist)
- [ ] `worker/tests/test_heartbeat.py` — stub for ANALYTICS-04 (heartbeat row pattern)
- [ ] `worker/tests/test_worker_loop.py` — stub for worker pgmq long-poll integration
- [ ] `web/vitest.config.ts` — vitest setup
- [ ] `web/tests/middleware-allowlist.test.ts` — stub for AUTH-02 (middleware rejects non-@syr.edu)
- [ ] `web/tests/auth-magic-link.spec.ts` — playwright/vitest stub for AUTH-01 (/me round-trip)
- [ ] `scripts/check-drift.sh` — drizzle-kit pull + datamodel-codegen diff against committed schema
- [ ] `scripts/eval-ci.sh` — run gold-set eval, compare to baseline, fail on regression or n_examples shrink
- [ ] `scripts/phase0-demo.sh` — exercises the 6-item exit demo end-to-end

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Resend DNS ticket filed with IT for IVMF subdomain | (demo item 6) | Org-side ticketing system, not in repo | Filed ticket URL pasted into `.planning/phases/00-foundation/00-EVIDENCE.md` with timestamp |
| Drift-trip PR fails CI in GitHub UI | (infra gating CANON-05/06/07/08) | Requires opening a real PR AND mutating live dev DB (psql ALTER) — see plan 06 task 4 | Branch with `psql -c "alter table public.businesses drop column normalized_name;"` then commit migration edit; push; screenshot failing check; restore via `psql -c "alter table public.businesses add column normalized_name text;"` |
| Eval-CI regression PR fails CI in GitHub UI | ANALYTICS-04 | Requires opening a real PR | Create branch lowering gold-set accuracy, push, screenshot failing check |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
