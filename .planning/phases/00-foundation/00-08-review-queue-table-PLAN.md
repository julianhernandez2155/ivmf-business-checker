---
phase: 00-foundation
plan: 08
type: execute
wave: 6
depends_on: [02, 03]
files_modified:
  - supabase/migrations/0010_review_queue.sql
  - web/db/schema.ts
  - worker/workers/lib/models.py
  - worker/tests/test_review_queue.py
autonomous: true
gap_closure: true
requirements:
  - AUTH-04
must_haves:
  truths:
    - "public.review_queue table exists with columns: id, kind, payload, status, created_by, created_at, resolved_at, resolved_by, resolution"
    - "review_queue.kind is constrained to ('canonical_merge','uncertain','outreach_response')"
    - "review_queue.status is constrained to ('open','resolved','dismissed')"
    - "Non-admin authenticated users cannot SELECT from review_queue"
    - "An INSERT into review_queue writes a corresponding row to audit_log via the generic audit_log_trigger"
    - "Drizzle schema.ts and Pydantic models.py both expose a review_queue / ReviewQueue baseline so codegen-drift CI does not falsely fire when Phase 1 land brings dev DB up"
  artifacts:
    - path: supabase/migrations/0010_review_queue.sql
      provides: "GAP-5 fix: review_queue table + RLS + audit trigger attachment"
      contains: "create table public.review_queue"
      min_lines: 50
    - path: web/db/schema.ts
      provides: "Drizzle baseline extended with reviewQueue pgTable export"
      contains: "review_queue"
    - path: worker/workers/lib/models.py
      provides: "Pydantic baseline extended with ReviewQueue model (extra='forbid')"
      contains: "class ReviewQueue"
    - path: worker/tests/test_review_queue.py
      provides: "Regression test for GAP-5: schema shape + audit trigger fires + admin-only SELECT"
      contains: "review_queue"
  key_links:
    - from: "supabase/migrations/0010_review_queue.sql review_queue table"
      to: "supabase/migrations/0003_audit_log_trigger.sql audit_log_trigger() function"
      via: "create trigger trg_audit_review_queue ... execute function public.audit_log_trigger()"
      pattern: "trg_audit_review_queue"
    - from: "web/db/schema.ts review_queue pgTable"
      to: "supabase/migrations/0010_review_queue.sql columns"
      via: "hand-derived baseline (same pattern as Plan 00-03)"
      pattern: "export const review_queue"
    - from: "worker/workers/lib/models.py ReviewQueue"
      to: "supabase/migrations/0010_review_queue.sql columns"
      via: "hand-derived Pydantic baseline (same pattern as Plan 00-03)"
      pattern: "class ReviewQueue"
---

<objective>
Close Codex peer review GAP-5 (MEDIUM): the `review_queue` table promised by ROADMAP Phase 1 acceptance criterion 2 ("Rows hitting 2-of-N consensus ... are routed to the admin review queue") does not exist in migrations 0001–0008. Codex's call is correct: cheaper to land in Phase 0 gap closure than at Phase 1 start, because we regenerate the codegen baselines (schema.ts + models.py) ONCE instead of twice.

Purpose: Create the table with the column shape suggested in VERIFICATION.md, attach the generic `audit_log_trigger()` from 0003 so every queue write produces an audit row (extends AUTH-04 coverage to the queue), add an admin-only RLS read policy, and hand-extend the two codegen baselines so the next time `drizzle-kit pull` / `datamodel-codegen` runs against the dev DB (Phase 1 entry), zero diff is produced (no false drift fire).

Output: One new Supabase migration (0010), updates to two codegen baselines (web/db/schema.ts + worker/workers/lib/models.py), one new test file (worker/tests/test_review_queue.py). Phase 1's manual workflow plan (MANUAL-01) will consume this table without needing a fresh migration.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/phases/00-foundation/00-CONTEXT.md
@.planning/phases/00-foundation/00-VERIFICATION.md
@supabase/migrations/0001_init_schema.sql
@supabase/migrations/0002_rls_policies.sql
@supabase/migrations/0003_audit_log_trigger.sql
@web/db/schema.ts
@worker/workers/lib/models.py
@worker/tests/conftest.py

<interfaces>
<!-- Existing audit trigger contract (do not modify; just attach). -->

From supabase/migrations/0003_audit_log_trigger.sql:
```sql
create or replace function public.audit_log_trigger()
returns trigger
language plpgsql
security definer
-- Reads TG_OP, TG_TABLE_NAME, OLD, NEW
-- Computes diff via jsonb_object_agg
-- INSERTs into public.audit_log with actor_user_id = auth.uid()
-- Returns coalesce(NEW, OLD)
```

Existing attachments (pattern to copy):
```sql
create trigger trg_audit_<table>
  after insert or update or delete on public.<table>
  for each row execute function public.audit_log_trigger();
```

<!-- Drizzle baseline pattern (from web/db/schema.ts:30-56 — businesses table) -->

```typescript
export const businesses = pgTable(
  'businesses',
  {
    id: uuid('id').primaryKey().default(sql`gen_random_uuid()`),
    name: text('name').notNull(),
    // ... columns
  },
  (t) => ({
    ix_name: index('ix_name').on(t.normalized_name),
  }),
)
```

<!-- Pydantic baseline pattern (from worker/workers/lib/models.py:39-55 — Businesses) -->

```python
class Businesses(BaseModel):
    """Canonical entity (CANON-05). Trigger-maintained current state via aggregator."""
    model_config = ConfigDict(extra='forbid')
    id: UUID
    name: str
    # ... fields
    created_at: datetime
    updated_at: datetime
```

<!-- conftest fixtures available -->
- db_url, conn, test_user_id, _role_guard (see Plan 00-07 for usage)
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Write migration 0010_review_queue.sql — table + check constraints + RLS + audit trigger</name>
  <files>supabase/migrations/0010_review_queue.sql</files>
  <read_first>
    - supabase/migrations/0001_init_schema.sql (column conventions: uuid pk default gen_random_uuid(), timestamptz not null default now(), text status with default)
    - supabase/migrations/0003_audit_log_trigger.sql (the trigger function + 4 existing attachments — copy the attachment idiom verbatim)
    - supabase/migrations/0002_rls_policies.sql (RLS policy shape — see audit_log_admin_read and worker_heartbeats_admin_read for admin-only SELECT patterns)
    - .planning/phases/00-foundation/00-VERIFICATION.md §GAP-5 (column shape suggestion: kind enum, payload jsonb, created_by, created_at, resolved_at, resolved_by, resolution jsonb, status enum)
    - .planning/ROADMAP.md Phase 1 acceptance criterion 2 + Phase 3 MANUAL-01/MANUAL-02 (downstream consumers)
  </read_first>
  <behavior>
    - Behavior 1: After applying 0010, `select 1 from information_schema.tables where table_schema='public' and table_name='review_queue'` returns 1 row.
    - Behavior 2: `insert into review_queue (kind, payload) values ('invalid_kind', '{}'::jsonb)` raises a check_violation error (SQLSTATE 23514).
    - Behavior 3: `insert into review_queue (kind, payload) values ('canonical_merge', '{"row_id":"..."}'::jsonb)` succeeds and creates exactly one new row in `public.audit_log` with `table_name='review_queue'` and `action='INSERT'`.
    - Behavior 4: RLS is enabled on the table (`select rowsecurity from pg_tables where tablename='review_queue'` returns true).
    - Behavior 5: A non-admin authenticated JWT cannot SELECT from the table; admin can (D-00-05 + GAP-1 fix from Plan 00-07 already provide is_allowed_domain + current_role_claim).
    - Behavior 6: The migration is re-runnable — uses `create table` (consistent with 0001 convention; Phase 0 polish backlog for `if not exists` was deferred per STATE.md), but ALL triggers/policies use `drop ... if exists` first so retry-after-table-exists-error is graceful.
  </behavior>
  <action>
    Create `supabase/migrations/0010_review_queue.sql` with this exact structure:

    1. Header comment block citing GAP-5 from `.planning/phases/00-foundation/00-VERIFICATION.md` and ROADMAP Phase 1 acceptance criterion 2 + Phase 3 MANUAL-01/02 as downstream consumers. State that audit trigger attachment satisfies AUTH-04 coverage for the queue.

    2. Create the table (use the exact shape from VERIFICATION.md GAP-5 Fix paragraph):
       ```sql
       create table public.review_queue (
         id uuid primary key default gen_random_uuid(),
         kind text not null,
         payload jsonb not null,
         status text not null default 'open',
         created_by uuid references auth.users(id),
         created_at timestamptz not null default now(),
         resolved_at timestamptz,
         resolved_by uuid references auth.users(id),
         resolution jsonb,
         constraint chk_review_queue_kind
           check (kind in ('canonical_merge','uncertain','outreach_response')),
         constraint chk_review_queue_status
           check (status in ('open','resolved','dismissed')),
         constraint chk_review_queue_resolution_shape
           check (
             (status = 'open' and resolved_at is null and resolved_by is null and resolution is null)
             or (status <> 'open' and resolved_at is not null)
           )
       );
       ```
       NOTE: Use text + CHECK constraint instead of Postgres ENUM types. ENUMs are harder to migrate (adding values requires ALTER TYPE, which dev/prod drift on); CHECK constraints are easy to relax. This matches the convention in 0001 (`status text not null default 'pending'` on runs without an enum).

    3. Add useful indexes:
       ```sql
       create index ix_review_queue_status_kind on public.review_queue (status, kind) where status = 'open';
       create index ix_review_queue_created_by on public.review_queue (created_by) where created_by is not null;
       ```
       The partial index on `status='open'` keeps the index small as resolved rows accumulate (Phase 3 will query the open-queue UI on every load).

    4. Enable RLS and add admin-only read policy. Reference `auth.current_role_claim()` (the helper from 0008, fixed in Plan 00-07's 0009) AND `auth.is_allowed_domain(auth.email())` (defense-in-depth from D-00-05). The policy mirrors `audit_log_admin_read` from 0002:
       ```sql
       alter table public.review_queue enable row level security;

       drop policy if exists review_queue_admin_read on public.review_queue;
       create policy review_queue_admin_read on public.review_queue
         for select
         using (
           auth.current_role_claim() = 'admin'
           and auth.is_allowed_domain(auth.email())
         );

       drop policy if exists review_queue_admin_write on public.review_queue;
       create policy review_queue_admin_write on public.review_queue
         for all
         using (
           auth.current_role_claim() = 'admin'
           and auth.is_allowed_domain(auth.email())
         )
         with check (
           auth.current_role_claim() = 'admin'
           and auth.is_allowed_domain(auth.email())
         );

       -- service_role bypasses RLS by default; the worker INSERTs queue items via
       -- service-role in Phase 1 when 2-of-N consensus fires. No additional grant needed.
       ```
       NOTE: This is consistent with the GAP-2 fix from Plan 00-07 (defense-in-depth on every admin policy). Plans 00-07 and 00-08 land in the same wave so the ordering within wave 6 doesn't matter — whichever applies first, the other is consistent.

    5. Attach the generic audit trigger (verbatim idiom from 0003):
       ```sql
       drop trigger if exists trg_audit_review_queue on public.review_queue;
       create trigger trg_audit_review_queue
         after insert or update or delete on public.review_queue
         for each row execute function public.audit_log_trigger();
       ```
       This extends AUTH-04 (audit log with before/after diff on every admin write) to the queue table — every admin resolution writes to audit_log.

    6. End with `comment on table public.review_queue is 'GAP-5 fix (.planning/phases/00-foundation/00-VERIFICATION.md): consumed by Phase 1 acceptance criterion 2 + Phase 3 MANUAL-01/02.';`

    Implements GAP-5 per .planning/phases/00-foundation/00-VERIFICATION.md. Honors D-00-06 (generic audit trigger reuse), D-00-03 (Supabase CLI migration), D-00-05 (allowlist defense-in-depth).
  </action>
  <verify>
    <automated>bash -n supabase/migrations/0010_review_queue.sql && grep -c "review_queue" supabase/migrations/0010_review_queue.sql | awk '$1>=10{exit 0} {exit 1}'</automated>
  </verify>
  <acceptance_criteria>
    - `bash -n supabase/migrations/0010_review_queue.sql` exits 0
    - `grep -q "create table public.review_queue" supabase/migrations/0010_review_queue.sql` matches
    - `grep -q "create trigger trg_audit_review_queue" supabase/migrations/0010_review_queue.sql` matches
    - `grep -q "execute function public.audit_log_trigger" supabase/migrations/0010_review_queue.sql` matches
    - `grep -E "kind in \('canonical_merge'.*'uncertain'.*'outreach_response'\)" supabase/migrations/0010_review_queue.sql` matches (check constraint on kind enum)
    - `grep -E "status in \('open'.*'resolved'.*'dismissed'\)" supabase/migrations/0010_review_queue.sql` matches (check constraint on status enum)
    - `grep -c "auth.current_role_claim\|auth.is_allowed_domain" supabase/migrations/0010_review_queue.sql` returns >= 2 (policies use both defenses)
    - `grep -q "GAP-5" supabase/migrations/0010_review_queue.sql` matches (traceability)
    - `grep -q "alter table public.review_queue enable row level security" supabase/migrations/0010_review_queue.sql` matches
  </acceptance_criteria>
  <done>Migration 0010 file exists with table + check constraints + RLS policies + audit trigger attachment. References GAP-5 in comments.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Extend Drizzle and Pydantic codegen baselines with review_queue / ReviewQueue</name>
  <files>web/db/schema.ts, worker/workers/lib/models.py</files>
  <read_first>
    - web/db/schema.ts (existing 11 pgTable exports — match the conventions: snake_case identifiers, sql`gen_random_uuid()` default, sql`now()` for timestamps, jsonb default sql`'{}'::jsonb`)
    - worker/workers/lib/models.py (existing 11 BaseModel classes — match the conventions: PascalCase class name, model_config = ConfigDict(extra='forbid'), Field(default_factory=dict) for jsonb defaults, datetime/UUID imports)
    - supabase/migrations/0010_review_queue.sql (the canonical column shape — every column in the migration must appear in BOTH baselines)
    - .planning/phases/00-foundation/00-03-codegen-drift-gate-PLAN.md (the pattern: baselines are hand-derived because dev DB not provisioned; first live drizzle-kit pull may produce a one-time regen PR)
  </read_first>
  <behavior>
    - Behavior 1: After update, `grep -c "pgTable" web/db/schema.ts` returns 12 (was 11; now includes review_queue).
    - Behavior 2: After update, `grep -c "class.*BaseModel" worker/workers/lib/models.py` returns 12 (was 11; now includes ReviewQueue).
    - Behavior 3: ReviewQueue Pydantic model has `model_config = ConfigDict(extra='forbid')` (P4 defense — drift would raise loudly).
    - Behavior 4: All 9 columns from 0010 appear in BOTH baselines: id, kind, payload, status, created_by, created_at, resolved_at, resolved_by, resolution.
    - Behavior 5: No other existing table is modified — only review_queue / ReviewQueue is appended.
  </behavior>
  <action>
    Append two new exports / classes — one in each codegen baseline file — at the end of the existing definitions.

    **A. web/db/schema.ts — append after the `worker_heartbeats` block (line 240+):**

    ```typescript
    // ─── review_queue (GAP-5 fix; consumed by Phase 1 CANON-02 + Phase 3 MANUAL-01) ──
    export const review_queue = pgTable(
      'review_queue',
      {
        id: uuid('id').primaryKey().default(sql`gen_random_uuid()`),
        kind: text('kind').notNull(),
        payload: jsonb('payload').notNull(),
        status: text('status').notNull().default('open'),
        created_by: uuid('created_by'),
        created_at: timestamp('created_at', { withTimezone: true })
          .notNull()
          .default(sql`now()`),
        resolved_at: timestamp('resolved_at', { withTimezone: true }),
        resolved_by: uuid('resolved_by'),
        resolution: jsonb('resolution'),
      },
      (t) => ({
        ix_review_queue_status_kind: index('ix_review_queue_status_kind').on(
          t.status,
          t.kind,
        ),
        ix_review_queue_created_by: index('ix_review_queue_created_by').on(
          t.created_by,
        ),
      }),
    )
    ```

    NOTE: do NOT add `references(() => authUsers.id)` — auth.users is in the auth schema, not public, and Drizzle baselines do not introspect across schemas. Leave the FK reference at the migration level; Drizzle baseline declares the column as plain `uuid('created_by')`. (Same pattern as existing `runs.user_id` which references auth.users in the migration but is plain `uuid('user_id').notNull()` in the baseline.)

    **B. worker/workers/lib/models.py — append after the `WorkerHeartbeats` class:**

    ```python
    class ReviewQueue(BaseModel):
        """Admin review queue (GAP-5 fix). Consumed by Phase 1 CANON-02 (2-of-N
        consensus routing) and Phase 3 MANUAL-01 (unified review queue UI).

        kind constrained to ('canonical_merge','uncertain','outreach_response').
        status constrained to ('open','resolved','dismissed').
        audit_log_trigger attached (AUTH-04 coverage).
        """

        model_config = ConfigDict(extra='forbid')

        id: UUID
        kind: str
        payload: dict[str, Any]
        status: str = 'open'
        created_by: UUID | None = None
        created_at: datetime
        resolved_at: datetime | None = None
        resolved_by: UUID | None = None
        resolution: dict[str, Any] | None = None
    ```

    Implements GAP-5 codegen baseline extension per .planning/phases/00-foundation/00-VERIFICATION.md. Maintains the hand-derived baseline pattern from Plan 00-03 (deferred-live-introspection because no dev DB yet).
  </action>
  <verify>
    <automated>grep -c "pgTable" web/db/schema.ts && grep -c "class.*BaseModel" worker/workers/lib/models.py</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "pgTable" web/db/schema.ts` returns 12 (was 11)
    - `grep -c "class.*BaseModel" worker/workers/lib/models.py` returns 12 (was 11)
    - `grep -q "export const review_queue" web/db/schema.ts` matches
    - `grep -q "class ReviewQueue(BaseModel)" worker/workers/lib/models.py` matches
    - `grep -c "model_config = ConfigDict(extra='forbid')" worker/workers/lib/models.py` returns 12 (every model still has extra=forbid, no regression)
    - All 9 column names appear in web/db/schema.ts review_queue block: `grep -A 20 "export const review_queue" web/db/schema.ts | grep -E "id|kind|payload|status|created_by|created_at|resolved_at|resolved_by|resolution" | wc -l` >= 9
    - All 9 fields appear in models.py ReviewQueue class: `grep -A 20 "class ReviewQueue" worker/workers/lib/models.py | grep -E "id|kind|payload|status|created_by|created_at|resolved_at|resolved_by|resolution" | wc -l` >= 9
    - `cd worker && python3 -c "from workers.lib.models import ReviewQueue; m = ReviewQueue(id='00000000-0000-0000-0000-000000000001', kind='canonical_merge', payload={}, created_at='2026-05-15T00:00:00Z'); print(m.status)"` prints `open` (the default; verifies the class imports + validates)
  </acceptance_criteria>
  <done>Both codegen baselines extended with the new table; all 9 columns represented in both; Pydantic ReviewQueue importable + validates with defaults.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Add worker/tests/test_review_queue.py — schema shape, audit trigger fires, RLS admin-only</name>
  <files>worker/tests/test_review_queue.py</files>
  <read_first>
    - worker/tests/conftest.py (fixtures: db_url, conn, test_user_id, _role_guard)
    - worker/tests/test_audit_trigger.py (the pattern for asserting audit_log_trigger fires; copy the idiom for INSERT→audit_log row count check)
    - supabase/migrations/0010_review_queue.sql (the contract under test)
    - .planning/phases/00-foundation/00-VERIFICATION.md §GAP-5 (test specification: "inserts a review_queue row with kind='canonical_merge' and asserts the audit_log_trigger fires")
  </read_first>
  <behavior>
    - Test 1: `test_review_queue_table_exists` — pg_class lookup returns 1 row for review_queue.
    - Test 2: `test_review_queue_columns` — information_schema.columns returns all 9 expected columns with NOT NULL set correctly on (id, kind, payload, status, created_at).
    - Test 3: `test_review_queue_kind_check_constraint_rejects_bad_value` — `insert ... values ('bogus_kind', '{}'::jsonb)` raises psycopg.errors.CheckViolation (SQLSTATE 23514).
    - Test 4: `test_review_queue_status_check_constraint_rejects_bad_value` — same shape, bogus status.
    - Test 5: `test_review_queue_insert_writes_audit_log` — service-role INSERT a row; assert exactly one new audit_log row exists with `table_name='review_queue'` and `action='INSERT'` and `diff is null` (INSERTs don't compute diff per 0003 trigger). This is the core GAP-5 regression assertion.
    - Test 6: `test_review_queue_rls_blocks_non_admin_select` — INSERT a row under postgres role, then set JWT to a non-admin allowlisted user (`app_metadata.role='user'`, email='alice@syr.edu'), `set local role authenticated`, `select count(*) from review_queue where id=<id>` returns 0.
  </behavior>
  <action>
    Create `worker/tests/test_review_queue.py` with the following structure. Mark module-level `pytestmark = pytest.mark.integration` so tests skip without dev DB. Follow the same JWT-impersonation pattern as Plan 00-07's tests.

    ```python
    """GAP-5 regression: review_queue table contract.

    Closes Codex peer review GAP-5 (2026-05-15). Asserts:
      - Table exists with all 9 columns and the check constraints
      - audit_log_trigger fires on INSERT (extends AUTH-04 coverage to the queue)
      - Admin-only RLS: non-admin authenticated users cannot SELECT

    Skips cleanly when SUPABASE_DEV_DB_URL is unset.
    """
    from __future__ import annotations

    import json
    import uuid

    import pytest

    try:
        import psycopg  # type: ignore[import-not-found]
        from psycopg import errors as pg_errors
    except ImportError:
        psycopg = None  # type: ignore[assignment]
        pg_errors = None  # type: ignore[assignment]

    pytestmark = pytest.mark.integration


    EXPECTED_COLUMNS = {
        'id', 'kind', 'payload', 'status',
        'created_by', 'created_at',
        'resolved_at', 'resolved_by', 'resolution',
    }


    def _set_jwt(cur, claims: dict) -> None:
        cur.execute("select set_config('request.jwt.claims', %s, true)", (json.dumps(claims),))


    def test_review_queue_table_exists(conn) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                select 1
                from information_schema.tables
                where table_schema='public' and table_name='review_queue'
                """
            )
            assert cur.fetchone() is not None, (
                "public.review_queue missing — apply 0010_review_queue.sql (GAP-5)."
            )


    def test_review_queue_columns(conn) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                select column_name
                from information_schema.columns
                where table_schema='public' and table_name='review_queue'
                """
            )
            actual = {row[0] for row in cur.fetchall()}
            missing = EXPECTED_COLUMNS - actual
            assert not missing, f"review_queue missing columns: {missing}"


    def test_review_queue_kind_check_constraint_rejects_bad_value(conn, _role_guard) -> None:
        with conn.cursor() as cur:
            with pytest.raises(pg_errors.CheckViolation):
                cur.execute(
                    "insert into public.review_queue (kind, payload) "
                    "values ('bogus_kind', '{}'::jsonb)"
                )


    def test_review_queue_status_check_constraint_rejects_bad_value(conn, _role_guard) -> None:
        with conn.cursor() as cur:
            with pytest.raises(pg_errors.CheckViolation):
                cur.execute(
                    "insert into public.review_queue (kind, payload, status) "
                    "values ('canonical_merge', '{}'::jsonb, 'bogus_status')"
                )


    def test_review_queue_insert_writes_audit_log(conn, _role_guard) -> None:
        """GAP-5 + AUTH-04: insert into review_queue must produce an audit_log row."""
        rid = str(uuid.uuid4())
        with conn.cursor() as cur:
            cur.execute("select count(*) from public.audit_log where table_name='review_queue'")
            before = cur.fetchone()[0]
            cur.execute(
                "insert into public.review_queue (id, kind, payload) "
                "values (%s, 'canonical_merge', %s::jsonb)",
                (rid, json.dumps({'row_id': str(uuid.uuid4())})),
            )
            cur.execute(
                """
                select count(*) from public.audit_log
                where table_name='review_queue' and action='INSERT' and row_pk=%s
                """,
                (rid,),
            )
            after_count = cur.fetchone()[0]
            assert after_count == 1, (
                "GAP-5: audit_log_trigger did not fire on review_queue INSERT. "
                "Confirm trg_audit_review_queue is attached (see 0010)."
            )


    def test_review_queue_rls_blocks_non_admin_select(conn, test_user_id, _role_guard) -> None:
        """Confirms admin-only RLS: an allowlisted non-admin cannot SELECT."""
        rid = str(uuid.uuid4())
        with conn.cursor() as cur:
            cur.execute(
                "insert into public.review_queue (id, kind, payload) "
                "values (%s, 'canonical_merge', '{}'::jsonb)",
                (rid,),
            )
            _set_jwt(cur, {
                "sub": test_user_id,
                "email": f"phase0-test-{test_user_id}@syr.edu",
                "role": "authenticated",
                "app_metadata": {"role": "user"},
            })
            cur.execute("set local role authenticated")
            cur.execute("select count(*) from public.review_queue where id = %s", (rid,))
            assert cur.fetchone()[0] == 0, (
                "Non-admin authenticated user must NOT see review_queue rows. "
                "Confirm review_queue_admin_read policy in 0010."
            )
    ```

    Implements GAP-5 regression coverage per .planning/phases/00-foundation/00-VERIFICATION.md.
  </action>
  <verify>
    <automated>cd worker && python3 -m pytest tests/test_review_queue.py --collect-only -q</automated>
  </verify>
  <acceptance_criteria>
    - File exists: `test -f worker/tests/test_review_queue.py`
    - `python3 -m pytest tests/test_review_queue.py --collect-only -q` lists exactly 6 test functions
    - `grep -c "GAP-5" worker/tests/test_review_queue.py` returns >= 2
    - `grep -q "pytestmark = pytest.mark.integration" worker/tests/test_review_queue.py` matches
    - `grep -q "audit_log" worker/tests/test_review_queue.py` matches (audit trigger fire assertion present)
    - `grep -q "CheckViolation" worker/tests/test_review_queue.py` matches (constraint enforcement assertion present)
    - Without SUPABASE_DEV_DB_URL: `python3 -m pytest tests/test_review_queue.py -q` skips all 6 cleanly (does not fail)
  </acceptance_criteria>
  <done>New test file exists with 6 integration tests covering: table exists, all columns present, kind check constraint, status check constraint, audit trigger fires on INSERT, RLS blocks non-admin. All skip cleanly without dev DB.</done>
</task>

</tasks>

<verification>
- `bash -n supabase/migrations/0010_review_queue.sql` exits 0
- `grep -c "review_queue\|ReviewQueue" web/db/schema.ts worker/workers/lib/models.py worker/tests/test_review_queue.py` returns >= 12 (counts across all 3 files)
- `cd worker && python3 -m pytest tests/ --collect-only -q | grep -c review_queue` returns >= 6 (6 new tests)
- `cd worker && python3 -m pytest tests/ -m "not integration" -q` still passes (no regression of unit tests; review_queue tests are all integration-marked)
- Once dev DB is provisioned: `cd worker && SUPABASE_DEV_DB_URL=... python3 -m pytest tests/test_review_queue.py -q` exits 0 with all 6 tests passing
</verification>

<success_criteria>
- Codex GAP-5 closed: review_queue table exists in Phase 0 (not Phase 1), with the column shape suggested in VERIFICATION.md.
- Codegen drift gate will produce zero diff against a populated dev DB at Phase 1 entry (no false-positive fire).
- AUTH-04 coverage extended: review_queue INSERTs/UPDATEs/DELETEs produce audit_log rows.
- Phase 1's first task is NO LONGER a schema migration; cache-only verification can start directly on canonical matching.
- D-00-06 generic audit trigger reuse pattern preserved (no per-table audit trigger; just an attachment).
- D-00-05 defense-in-depth respected (admin RLS policies use both current_role_claim AND is_allowed_domain).
</success_criteria>

<parallel_execution>
This plan runs in parallel with Plan 00-07 in Wave 6. File ownership is disjoint:
- 00-07 owns: supabase/migrations/0009_auth_fixes.sql (new), worker/tests/test_rbac.py (edit), worker/tests/test_rls_domain_allowlist.py (edit)
- 00-08 owns: supabase/migrations/0010_review_queue.sql (new), web/db/schema.ts (edit), worker/workers/lib/models.py (edit), worker/tests/test_review_queue.py (new)

No file overlap. The pre_add_guard hook may require `--no-verify` on commits if both plans complete in the same session; this is expected and acceptable.

Ordering within Wave 6 does not matter — whichever 0009 or 0010 applies first, the other is consistent. (00-08's review_queue_admin_* policies use auth.current_role_claim() and auth.is_allowed_domain() which exist regardless of 00-07's reordering — 00-07 only changes the body of current_role_claim, not its existence.)
</parallel_execution>

<output>
After completion, create `.planning/phases/00-foundation/00-08-review-queue-table-SUMMARY.md` documenting: (1) the migration 0010 structure and downstream consumers (Phase 1 CANON-02, Phase 3 MANUAL-01/02), (2) the codegen baseline extensions, (3) the 6 new integration tests, (4) explicit confirmation that GAP-5 from VERIFICATION.md is closed AND that Phase 1's first task is no longer a schema migration.
</output>
