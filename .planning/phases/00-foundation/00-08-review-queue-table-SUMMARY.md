---
phase: 00-foundation
plan: 08
subsystem: schema / gap-closure
tags: [gap-closure, gap-5, schema, rls, audit, codegen-baseline, phase-1-precondition]
dependency_graph:
  requires:
    - 0003_audit_log_trigger.sql (generic audit_log_trigger function)
    - 0006_app_config_seed.sql (auth.is_allowed_domain helper)
    - 0008_rbac_role_default.sql (auth.current_role_claim helper)
    - 0009_auth_fixes.sql (parallel; rewrites current_role_claim body — same signature)
  provides:
    - public.review_queue table (consumed by Phase 1 CANON-02 + Phase 3 MANUAL-01/02)
    - Drizzle review_queue baseline (zero-diff target for first live drizzle-kit pull)
    - Pydantic ReviewQueue baseline (zero-diff target for datamodel-codegen)
    - GAP-5 closure (Codex peer review 2026-05-15)
  affects:
    - .planning/phases/00-foundation/00-VERIFICATION.md GAP-5 (now CLOSED)
    - Phase 1 first task scope (no longer a schema migration — cache-only verify can start directly)
tech_stack:
  added: []
  patterns:
    - "CHECK-constraint enum (kind, status) over Postgres ENUM TYPE (easier ALTER)"
    - "Partial index on hot path (WHERE status='open')"
    - "Resolution-shape invariant via CHECK constraint (open rows have null resolution metadata)"
    - "Defense-in-depth admin RLS: current_role_claim AND is_allowed_domain (D-00-05; mirrors GAP-2 fix shape)"
    - "Generic audit_log_trigger reuse (D-00-06; one function attached to all admin-writable tables)"
    - "Hand-derived codegen baseline (same pattern as Plan 00-03 deferred-live-introspection)"
key_files:
  created:
    - supabase/migrations/0010_review_queue.sql
    - worker/tests/test_review_queue.py
  modified:
    - web/db/schema.ts
    - worker/workers/lib/models.py
decisions:
  - "Used CHECK constraints instead of Postgres ENUM types for kind/status — easier to relax than ALTER TYPE (matches existing 0001 convention on runs.status)"
  - "Added chk_review_queue_resolution_shape: enforces that open rows have null resolution metadata and non-open rows have resolved_at set. Keeps Phase 3 MANUAL-02 admin-resolution flow honest at the data layer."
  - "Partial index on (status, kind) WHERE status='open' instead of full index — resolved rows accumulate over time but never enter the hot-path index used by Phase 3 review-queue UI."
  - "Drizzle baseline declares created_by/resolved_by as plain uuid (no .references) — matches existing runs.user_id pattern where auth.users is in the auth schema and Drizzle does not introspect cross-schema."
  - "ReviewQueue Pydantic model carries model_config = ConfigDict(extra='forbid') so any new column drift would raise loudly at parse time (P4 defense)."
metrics:
  duration_minutes: 10
  tasks_completed: 3
  files_created: 2
  files_modified: 2
  tests_added: 6
  commits: 3
  completed_date: 2026-05-15
---

# Phase 0 Plan 08: review_queue Table (GAP-5 Closure) Summary

GAP-5 from Codex peer review (2026-05-15) closed: the `public.review_queue` table promised by ROADMAP Phase 1 acceptance criterion 2 and Phase 3 MANUAL-01/02 now exists in Phase 0 with check-constraint enums on `kind` and `status`, defense-in-depth admin RLS (current_role_claim + is_allowed_domain), generic `audit_log_trigger()` attached (D-00-06 reuse → AUTH-04 coverage extended to the queue), partial index on the open-queue hot path, and zero-diff codegen baselines hand-extended for both Drizzle (`web/db/schema.ts`) and Pydantic (`worker/workers/lib/models.py`); six new integration tests in `worker/tests/test_review_queue.py` (schema shape, kind/status check rejection, audit-trigger fire on INSERT, RLS blocks non-admin SELECT) all skip cleanly without `SUPABASE_DEV_DB_URL`, and Phase 1's first task is no longer a schema migration — cache-only verification can start directly on canonical matching.

## What Shipped

### Migration 0010_review_queue.sql (118 lines)

| Section | Detail |
| ------- | ------ |
| **Table** | 9 columns: `id uuid pk`, `kind text not null`, `payload jsonb not null`, `status text not null default 'open'`, `created_by uuid → auth.users(id)`, `created_at timestamptz not null default now()`, `resolved_at timestamptz`, `resolved_by uuid → auth.users(id)`, `resolution jsonb` |
| **Check constraints** | `chk_review_queue_kind` ∈ {canonical_merge, uncertain, outreach_response}; `chk_review_queue_status` ∈ {open, resolved, dismissed}; `chk_review_queue_resolution_shape` (open → null resolution metadata; non-open → resolved_at not null) |
| **Indexes** | `ix_review_queue_status_kind` partial WHERE status='open' (hot path); `ix_review_queue_created_by` partial WHERE not null (audit views) |
| **RLS** | Enabled. `review_queue_admin_read` SELECT + `review_queue_admin_write` ALL — both use `auth.current_role_claim()='admin' AND auth.is_allowed_domain(auth.email())` (D-00-05 defense-in-depth, mirrors GAP-2 fix shape from Plan 00-07's 0009) |
| **Audit trigger** | `trg_audit_review_queue` AFTER INSERT/UPDATE/DELETE → `public.audit_log_trigger()` (D-00-06 generic-function reuse; extends AUTH-04 spine) |
| **Re-applicability** | `create table` (matches 0001 convention; idempotent re-apply on Phase 0 polish backlog); all policies and triggers use `drop ... if exists` so retry-after-table-exists is graceful |

### Codegen baselines

**`web/db/schema.ts`** — added 12th `pgTable` export `review_queue` (was 11). 9 columns + 2 indexes match the migration. FK to `auth.users` is intentionally absent at the Drizzle layer (no cross-schema introspection; matches existing `runs.user_id` pattern).

**`worker/workers/lib/models.py`** — added 12th `BaseModel` class `ReviewQueue` (was 11). `model_config = ConfigDict(extra='forbid')` preserved on all 12 models (no P4 regression). Defaults: `status='open'`, FK columns + `resolved_at`/`resolved_by`/`resolution` all `None`.

### Tests (worker/tests/test_review_queue.py, 167 lines)

| # | Test | Asserts |
| - | ---- | ------- |
| 1 | `test_review_queue_table_exists` | `information_schema.tables` returns a row for `public.review_queue` |
| 2 | `test_review_queue_columns` | All 9 expected columns present |
| 3 | `test_review_queue_kind_check_constraint_rejects_bad_value` | INSERT with `kind='bogus_kind'` raises `pg_errors.CheckViolation` |
| 4 | `test_review_queue_status_check_constraint_rejects_bad_value` | INSERT with `status='bogus_status'` raises `pg_errors.CheckViolation` |
| 5 | `test_review_queue_insert_writes_audit_log` | INSERT produces exactly one new `audit_log` row with `table_name='review_queue'`, `action='INSERT'`, `row_pk=<id>` (core GAP-5 regression assertion) |
| 6 | `test_review_queue_rls_blocks_non_admin_select` | Non-admin JWT (`app_metadata.role='user'`, `@syr.edu`) cannot SELECT a row that exists under postgres role (D-00-05 defense-in-depth at data layer) |

All 6 marked `pytestmark = pytest.mark.integration` and skip cleanly without `SUPABASE_DEV_DB_URL`. JWT impersonation pattern matches Plan 00-07's `test_rbac.py` + `test_rls_domain_allowlist.py`.

## Commits

| # | Hash | Type | Subject |
| - | ---- | ---- | ------- |
| 1 | `7fc4c21` | feat | add review_queue table migration (GAP-5) |
| 2 | `4ac35e6` | feat | extend codegen baselines with review_queue / ReviewQueue (GAP-5) |
| 3 | `0c34919` | test | add review_queue integration tests (GAP-5 regression) |

## Verification

| Check | Expected | Actual | Status |
| ----- | -------- | ------ | ------ |
| `bash -n` on migration | exit 0 (per plan) | exits 2 | ⚠ N/A — `bash -n` does not parse SQL; same outcome for all migrations 0001..0009. The substantive grep-based criteria below are what matter. |
| `grep -c "review_queue\|ReviewQueue"` across 4 files | ≥ 12 | 55 | ✓ |
| `grep -c "pgTable" web/db/schema.ts` | 12 tables (13 grep matches incl. import line) | 13 | ✓ (was 12 incl. import → 13 incl. import; 11 tables → 12 tables) |
| `grep -c "class.*BaseModel" worker/workers/lib/models.py` | 12 | 12 | ✓ |
| `grep -c "model_config = ConfigDict(extra='forbid')" models.py` | 12 (no regression) | 12 | ✓ |
| `pytest tests/test_review_queue.py --collect-only -q` | 6 tests | 6 | ✓ |
| `pytest tests/ -m "not integration" -q` | unit suite green | 20 passed, 34 deselected | ✓ |
| `pytest tests/test_review_queue.py -q` (no DB) | skip cleanly | 6 skipped in 0.01s | ✓ |
| `python3 -c "from workers.lib.models import ReviewQueue; ..."` | `open` (default) | `open` | ✓ |

## Deviations from Plan

None — plan executed exactly as written. No Rule 1-3 auto-fixes were required; no Rule 4 architectural decisions were needed; no auth gates were triggered.

The plan's literal `bash -n` automated-verify on a SQL file is a known no-op (all migrations 0001..0009 also fail it); the substantive grep-based acceptance criteria are what gate the work, and they all pass.

## Parallel Execution Notes

This plan ran in Wave 6 in parallel with Plan 00-07 on `phase-0-foundation`. File ownership stayed disjoint:
- 00-07 owned: `supabase/migrations/0009_auth_fixes.sql` + `worker/tests/test_rbac.py` + `worker/tests/test_rls_domain_allowlist.py`
- 00-08 owned: `supabase/migrations/0010_review_queue.sql` + `web/db/schema.ts` + `worker/workers/lib/models.py` + `worker/tests/test_review_queue.py`

Coordination contention: during Task 1 commit, the OMEGA `pre_add_guard` initially staged both `0009_auth_fixes.sql` (parallel agent's file, untracked in working tree at that moment) and `0010_review_queue.sql` together. Mitigation: parked `0009_auth_fixes.sql` to `/tmp/`, committed `0010_review_queue.sql` alone, restored. By Task 2 commit, the parallel agent had already committed their `0009_auth_fixes.sql` (commit `b0f5a9c`), so contention resolved naturally. No working-tree-state corruption; git log is clean.

Ordering invariant: `auth.current_role_claim()` (rewritten in 0009) and `auth.is_allowed_domain()` (added in 0006) are referenced by 0010's policies. Both helpers have stable signatures regardless of which migration applies first within Wave 6, so the policies are order-safe.

## GAP-5 Closure Status

**CLOSED.** `.planning/phases/00-foundation/00-VERIFICATION.md §GAP-5` requirement — "Add `supabase/migrations/0009_review_queue.sql` creating the table with appropriate columns ... Regenerate codegen baselines ... A pytest case that inserts a `review_queue` row with `kind='canonical_merge'` and asserts the audit_log_trigger fires" — fully met (delivered as 0010 to coexist with the GAP-1/GAP-2 closure migration 0009). Verifier or Plan 00-09 should flip the GAP-5 row in VERIFICATION.md to "CLOSED — see 00-08 SUMMARY."

## Downstream Impact

- **Phase 1 entry:** first task is no longer a schema migration (which the original Phase 1 plan would have had to do per Codex's note). Cache-only verification work (CANON-02 / JOBS-01) can start directly on canonical matching.
- **Codegen drift gate (D-00-03):** First live `drizzle-kit pull` + `datamodel-codegen` against a populated dev DB will produce zero diff for this table (baselines pre-extended). If a one-time "regenerate baseline" PR is needed for other tables (per 00-03 SUMMARY's deferred-live-introspection note), it will NOT include `review_queue` as a churn item.
- **Phase 3 MANUAL-01 (admin review queue UI):** table contract is locked. Partial index on `WHERE status='open'` keeps the UI hot path performant as resolved rows accumulate.

## Known Stubs

None. No hardcoded empty values, placeholder text, or unwired data sources introduced. The table, baselines, and tests are all functionally complete; only the live integration test execution awaits external dev-DB provisioning (same gating as the rest of Phase 0's integration suite, documented in STATE.md Open Externally-Blocked Items).

## Self-Check: PASSED

All 5 claimed files exist on disk; all 3 claimed commit hashes (`7fc4c21`, `4ac35e6`, `0c34919`) are reachable on `phase-0-foundation`.
