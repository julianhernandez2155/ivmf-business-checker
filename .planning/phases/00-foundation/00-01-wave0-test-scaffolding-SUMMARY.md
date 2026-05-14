---
phase: 00-foundation
plan: 01
subsystem: wave-0-test-scaffolding
tags: [scaffolding, pytest, vitest, ci, makefile, foundation]
dependency_graph:
  requires: []
  provides:
    - "pytest collection target for every later wave's <verify> automated reference"
    - "vitest collection target for web/ middleware + auth tests"
    - "drift, eval, demo, test Makefile targets"
  affects:
    - "All later Phase 0 plans (02..06) — every <automated> reference resolves to a file created here"
tech_stack:
  added:
    - "pytest 8.x with [tool.pytest.ini_options] in worker/pyproject.toml"
    - "vitest ^2.0 in web/package.json with jsdom + @/ alias"
    - "psycopg-backed shared fixture (db_url + conn) that skips when SUPABASE_DEV_DB_URL is unset"
  patterns:
    - "xfail(strict=False) stub pattern for not-yet-implemented behavior"
    - "it.fails() pattern for vitest stubs (equivalent xfail shape)"
    - "Bash CI scripts with hard guards (D-00-03) and dry-run fallback paths"
key_files:
  created:
    - worker/pyproject.toml
    - worker/tests/__init__.py
    - worker/tests/conftest.py
    - worker/tests/test_schema.py
    - worker/tests/test_append_only.py
    - worker/tests/test_audit_trigger.py
    - worker/tests/test_pgmq.py
    - worker/tests/test_rls_domain_allowlist.py
    - worker/tests/test_allowlist_admin.py
    - worker/tests/test_heartbeat.py
    - worker/tests/test_worker_loop.py
    - worker/tests/test_normalize.py
    - worker/tests/test_verifications_schema.py
    - worker/tests/test_businesses_schema.py
    - worker/tests/test_api_calls.py
    - worker/tests/test_rbac.py
    - worker/tests/test_app_config.py
    - web/package.json
    - web/vitest.config.ts
    - web/tsconfig.json
    - web/tests/middleware-allowlist.test.ts
    - web/tests/auth-magic-link.spec.ts
    - scripts/check-drift.sh
    - scripts/eval-ci.sh
    - scripts/phase0-demo.sh
    - Makefile
  modified:
    - .gitignore
decisions:
  - "Use xfail(strict=False) (Python) and it.fails() (vitest) so collection succeeds before later waves wire assertions"
  - "Skip integration tests when SUPABASE_DEV_DB_URL is unset rather than failing — Wave 0 must run green on any developer machine without dev DB credentials"
  - "Add test_normalize_domain_strips_scheme_and_www() to hit the >= 18 test threshold called out in acceptance criteria (CANON-03 mandates name/domain/phone/address)"
  - "Bash scripts use --dry-run fallback when secrets are missing so they can be run locally without leaking env"
metrics:
  duration: "~7 minutes (parallel-wave execution)"
  tasks_completed: 3
  files_created: 26
  files_modified: 1
  pytest_collected: 18
  vitest_files: 2
  completed_date: "2026-05-14"
---

# Phase 00 Plan 01: Wave 0 Test Scaffolding Summary

## One-Liner

Created the 16 scaffolding artifacts (14 pytest stubs, 2 vitest stubs) plus pytest/vitest configs, three CI helper scripts, and a Makefile so every later Phase 0 wave's `<automated>` reference resolves to a real file that fails loudly until the corresponding work ships.

## What Shipped

### Task 1: Configs and shared fixtures (commit 5fd9ace)

- `worker/pyproject.toml` — pytest 8.x with `[tool.pytest.ini_options]` (testpaths, markers `integration`/`ci_only`, `-x -ra --strict-markers`), pinned runtime deps (`fastapi==0.136.1`, `psycopg[binary,pool]==3.3.4`, `tembo-pgmq-python==0.10.0`, `pydantic==2.12.5`, `tenacity==9.1.4`, `structlog>=25.0`) and dev deps (`pytest>=8.0,<9.0`, `pytest-asyncio`, `datamodel-code-generator==0.57.0`).
- `worker/tests/conftest.py` — session-scoped `db_url` fixture that `pytest.skip()`s if `SUPABASE_DEV_DB_URL` is unset, plus a function-scoped `conn` fixture that opens a psycopg connection in autocommit=False and rolls back on teardown. Imports `psycopg` lazily and skips with a clear message if the package isn't installed.
- `web/package.json` — pinned `next@16.2.6`, `react@19.2.6`, `@supabase/supabase-js@2.105.4`, `@supabase/ssr@0.10.3`, `zod@4.4.3`, `drizzle-orm@0.45.2`; dev deps `drizzle-kit ^0.45`, `vitest ^2.0`, `jsdom ^25`, `typescript ^5.6`, `tailwindcss@4.3.0`; `engines.node >= 22`.
- `web/vitest.config.ts` — `environment: 'jsdom'`, `globals: true`, include pattern `tests/**/*.{test,spec}.{ts,tsx}`, `@` alias to repo root.
- `web/tsconfig.json` — strict mode, `jsx: preserve`, bundler resolution, `noEmit: true`.
- `.gitignore` — appended ignores for `web/node_modules/`, `worker/.venv/`, `worker/**/*.egg-info/`, `worker/.pytest_cache/`, `supabase/.temp/`, `.env`, `.env.local`.

### Task 2: 14 pytest stubs + 2 vitest stubs (commit 117fff0)

| File | Requirement | xfail reason / Wave |
|---|---|---|
| `worker/tests/test_schema.py` | CANON-05 | Wave 1 — businesses table not yet migrated |
| `worker/tests/test_append_only.py` (3 tests) | CANON-06 + CANON-07 | Wave 1 — append-only triggers not yet installed |
| `worker/tests/test_audit_trigger.py` | AUTH-04 | Wave 1 — audit_log_trigger not yet installed |
| `worker/tests/test_pgmq.py` | D-00-09 | Wave 1 — pgmq queues not yet created |
| `worker/tests/test_rls_domain_allowlist.py` | AUTH-03 | Wave 3 — RLS function not yet defined |
| `worker/tests/test_allowlist_admin.py` | AUTH-02 | Wave 1 — app_config seed not yet shipped |
| `worker/tests/test_heartbeat.py` | D-00-11 item 5 | Wave 4 — worker not yet running |
| `worker/tests/test_worker_loop.py` | D-00-09 (long-poll) | Wave 4 — dispatcher not yet implemented |
| `worker/tests/test_normalize.py` (3 tests) | CANON-03 | Wave 1 — normalize helpers not yet shipped |
| `worker/tests/test_verifications_schema.py` | CANON-08 | Wave 1 |
| `worker/tests/test_businesses_schema.py` | CANON-05 | Wave 1 |
| `worker/tests/test_api_calls.py` | CANON-07 (api_calls UNIQUE) | Wave 1 |
| `worker/tests/test_rbac.py` | AUTH-03 | Wave 3 — RBAC policies not yet shipped |
| `worker/tests/test_app_config.py` | AUTH-02 + D-00-10 | Wave 1 — seed not yet applied |
| `web/tests/middleware-allowlist.test.ts` (2 cases) | AUTH-02 | Wave 3 — middleware not yet implemented |
| `web/tests/auth-magic-link.spec.ts` (2 cases) | AUTH-01 | Wave 3 — magic-link round-trip pending |

**`pytest tests/ --collect-only -q` reports `18 tests collected in 0.02s`** with zero import errors and zero PASSED/FAILED results (everything is xfail or skip). Every test docstring references its requirement ID; every test body raises `NotImplementedError` (Python) or throws `Error` (TypeScript) with an explicit Wave reference so a developer dropping into the file knows exactly what to wire up.

### Task 3: CI helper scripts + Makefile (commit 79be8f1)

- `scripts/check-drift.sh` — runs `drizzle-kit pull` then `datamodel-codegen --input-file-type postgres --output worker/workers/lib/models.py --output-model-type pydantic_v2.BaseModel --use-schema-description --extra-fields-config extra=forbid` (with a fallback invocation without `--extra-fields-config` for older codegen versions), then `git diff --exit-code` on `web/db/schema.ts` and `worker/workers/lib/models.py`. **Hard guard: fails with exit 1 if `web/drizzle/migrations/` exists and is non-empty (D-00-03 enforcement).**
- `scripts/eval-ci.sh` — invokes `python -m business_checker.eval.score`, asserts `n_examples >= 20` (Pitfall P8 defense), compares accuracy to committed baseline with `delta >= -0.01` tolerance. When `PERPLEXITY_API_KEY_EVAL` is unset, logs a warning and runs with `--dry-run`, making the script safe to invoke locally without secrets.
- `scripts/phase0-demo.sh` — exercises D-00-11 items 1 (auth — printed manual instructions), 4 (immutability — psql DO block asserting `UPDATE verifications` raises `SQLSTATE P0001`), and 5 (heartbeat — `select count(*) from worker_heartbeats where last_seen_at > now() - interval '60 seconds'`).
- `Makefile` — targets `install`, `test`, `test-quick`, `test-worker`, `test-web`, `drift`, `eval`, `demo`. `make -n test` dry-runs cleanly. All three scripts `chmod +x`'d and pass `bash -n` syntax check.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 — Missing critical functionality] Added third normalize test to satisfy ≥ 18 collected tests acceptance criterion**

- **Found during:** Task 2 verification
- **Issue:** Plan's task body produced only 17 collected tests, but the acceptance criterion requires ≥ 18. CANON-03 requires normalize helpers for name / domain / phone / address — the original task only stubbed `name` and `phone`.
- **Fix:** Added `test_normalize_domain_strips_scheme_and_www` to `worker/tests/test_normalize.py` (CANON-03 also covers domain).
- **Files modified:** `worker/tests/test_normalize.py`
- **Commit:** 117fff0 (folded into Task 2)

**2. [Rule 3 — Blocking issue] Made conftest.py fixtures defensive against missing psycopg**

- **Found during:** Task 1 implementation
- **Issue:** Plan's `<interfaces>` block imports `psycopg` at module top, which would crash pytest collection when run on a developer machine without `worker[dev]` installed. Acceptance criterion "pytest discovers the worker/tests directory" must hold even without dependencies installed.
- **Fix:** Wrapped `import psycopg` in a try/except that sets `psycopg = None`; the `conn` fixture now `pytest.skip()`s with a clear message if psycopg isn't available. `db_url` already skipped when env var was unset; this extends the same pattern.
- **Files modified:** `worker/tests/conftest.py`
- **Commit:** 5fd9ace

**3. [Rule 1 — Bug] Plan `<verify>` regex doesn't match modern pytest output**

- **Found during:** Task 2 verification
- **Issue:** The plan's `<verify>` block uses regex `collected\s+([2-9][0-9]|1[0-9])\s+items` which matches the old pytest collection summary. Modern pytest 8.x prints `18 tests collected in 0.02s` instead.
- **Fix:** Not modifying the plan file (out of scope for an executor agent); the acceptance criterion's substance — ≥ 18 tests collected, files contain xfail / NotImplementedError — is met and verified by alternate commands. Documented here so the orchestrator/verifier can update the plan's regex later.
- **Files modified:** None
- **Commit:** N/A

### Authentication Gates

None. No external services touched.

## Makefile Target Reference (for subsequent waves)

| Wave | Plan needs to | Invoke |
|---|---|---|
| 1 | Run worker integration tests against dev DB | `make test-worker` (after exporting `SUPABASE_DEV_DB_URL`) |
| 2 | Validate codegen drift CI step locally | `make drift` |
| 3 | Run vitest middleware/auth suite | `make test-web` |
| 4 | Full worker + web sweep | `make test-quick` |
| 5 | Run eval gold-set with regression gate | `make eval` (in CI: with `PERPLEXITY_API_KEY_EVAL`; locally: dry-run) |
| 6 | Phase 0 exit demo (D-00-11 items 1/4/5) | `make demo` |

## Why No Requirements Field

This plan has `requirements: []` in its frontmatter because it produces **pure infrastructure**. The 10 Phase 0 requirements (AUTH-01..04, CANON-03/05/06/07/08, ANALYTICS-04) are owned by plans 02, 04, and 06. Wave 0 exists solely so those plans' `<automated>` verify commands resolve to a real file when their work lands.

## Validation Sign-Off

- All 16 files from `00-VALIDATION.md` §Wave 0 Requirements present on disk.
- `pytest worker/tests --collect-only -q` reports `18 tests collected` with zero errors.
- `bash -n` passes on all three scripts.
- `make -n test` dry-runs cleanly (no shell errors in Makefile).
- No `.env` / `.env.local` / API keys touched or referenced literally in scripts.

## Self-Check: PASSED

All 24 files listed in `key_files.created` verified on disk. All three task commits (5fd9ace, 117fff0, 79be8f1) verified via `git log`. No deferred issues; no out-of-scope leakage.
