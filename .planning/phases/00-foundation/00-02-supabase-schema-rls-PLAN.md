---
phase: 00-foundation
plan: 02
type: execute
wave: 1
depends_on: [01]
files_modified:
  - supabase/config.toml
  - supabase/migrations/0001_init_schema.sql
  - supabase/migrations/0002_rls_policies.sql
  - supabase/migrations/0003_audit_log_trigger.sql
  - supabase/migrations/0004_verifications_append_only.sql
  - supabase/migrations/0005_pgmq_queues.sql
  - supabase/migrations/0006_app_config_seed.sql
  - supabase/migrations/0007_worker_heartbeats.sql
  - worker/.env.example
  - worker/tests/conftest.py
  - worker/tests/test_schema.py
  - worker/tests/test_append_only.py
  - worker/tests/test_audit_trigger.py
  - worker/tests/test_pgmq.py
  - worker/tests/test_app_config.py
  - worker/tests/test_api_calls.py
  - worker/tests/test_verifications_schema.py
  - worker/tests/test_businesses_schema.py
  - worker/tests/test_normalize.py
  - worker/workers/lib/normalize.py
autonomous: true
requirements:
  - CANON-03
  - CANON-05
  - CANON-06
  - CANON-07
  - CANON-08
  - AUTH-04
must_haves:
  truths:
    - "Supabase dev project contains businesses, verifications, run_rows, runs, api_calls, app_config, api_keys, budget_ledger, audit_log, outreach_tickets (stub), worker_heartbeats tables"
    - "UPDATE verifications raises SQLSTATE P0001; DELETE verifications raises SQLSTATE P0001"
    - "Duplicate INSERT same (run_id, row_index, pass) on verifications raises SQLSTATE 23505"
    - "Duplicate INSERT same (provider, request_hash) on api_calls raises SQLSTATE 23505"
    - "UPDATE on app_config writes a row to audit_log with non-null diff jsonb"
    - "pgmq.q_verify and pgmq.q_aggregator exist; visible in pgmq.meta"
    - "app_config has seed row email_domain_allowlist=['syr.edu'] and column_allowlist for BMSG/MWBE headers"
    - "Normalize helpers (name/domain/phone/address) return deterministic outputs for known fixtures"
  artifacts:
    - path: supabase/migrations/0001_init_schema.sql
      provides: "All Phase 0 tables (businesses, verifications, runs, run_rows, api_calls, app_config, api_keys, budget_ledger, outreach_tickets stub)"
      min_lines: 80
    - path: supabase/migrations/0003_audit_log_trigger.sql
      provides: "Generic audit_log_trigger() + attachments per D-00-06"
      contains: "audit_log_trigger"
    - path: supabase/migrations/0004_verifications_append_only.sql
      provides: "BEFORE UPDATE/DELETE raise triggers + UNIQUE constraint"
      contains: "verifications is append-only"
    - path: supabase/migrations/0005_pgmq_queues.sql
      provides: "pgmq.create('q_verify') and pgmq.create('q_aggregator')"
      contains: "pgmq.create"
    - path: worker/workers/lib/normalize.py
      provides: "normalize_name, normalize_domain, normalize_phone, normalize_address (stub) helpers"
      min_lines: 40
  key_links:
    - from: "supabase/migrations/0003_audit_log_trigger.sql"
      to: "app_config, api_keys, budget_ledger, outreach_tickets"
      via: "trigger attachment"
      pattern: "create trigger trg_audit_"
    - from: "supabase/migrations/0004_verifications_append_only.sql"
      to: "public.verifications"
      via: "BEFORE UPDATE/DELETE trigger"
      pattern: "before (update|delete) on public.verifications"
    - from: "worker/tests/test_append_only.py"
      to: "verifications + api_calls tables"
      via: "psycopg fixture from conftest.py"
      pattern: "from psycopg|conn.cursor"
---

<objective>
Land the entire Phase 0 schema on the dev Supabase project: all tables, the append-only triggers, idempotency UNIQUE constraints, generic audit_log trigger, pgmq queue creation, app_config seed rows, and the worker_heartbeats table. Wire the Wave 0 test stubs to real assertions. Ship the normalize helper module (CANON-03 lands here, not in Wave 5).

Purpose: This is the highest-leverage plan in Phase 0. Six of the ten phase requirements ship here (CANON-03/05/06/07/08, AUTH-04). The schema gate must be green before codegen (Wave 2), auth (Wave 3), or the worker (Wave 4) can ship.

Output: 7 migration files applied to dev Supabase, the normalize.py module with passing unit tests, and 8 of the 14 worker test stubs converted from xfail to real green assertions.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/ROADMAP.md
@.planning/phases/00-foundation/00-CONTEXT.md
@.planning/phases/00-foundation/00-RESEARCH.md
@.planning/research/ARCHITECTURE.md
@.planning/research/PITFALLS.md
@.planning/phases/00-foundation/00-01-wave0-test-scaffolding-SUMMARY.md

<interfaces>
<!-- The schema column shapes derived from CONTEXT.md decisions and ARCHITECTURE.md inventory -->
<!-- Executor uses these verbatim — no codebase exploration needed. -->

Tables to create in 0001_init_schema.sql (columns are AUTHORITATIVE — use exactly):

```sql
-- businesses (canonical entity)
create table public.businesses (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  normalized_name text,
  ein text,
  website_domain text,
  phone_e164 text,
  address_normalized jsonb,
  city text,
  state text,
  match_signals jsonb default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index ix_businesses_normalized_name on public.businesses (normalized_name);
create index ix_businesses_ein on public.businesses (ein) where ein is not null;

-- runs (per upload)
create table public.runs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id),
  status text not null default 'pending',  -- pending/parsing/running/paused/completed/errored
  source_filename text,
  row_count integer,
  cost_estimate_cents integer default 0,
  cost_actual_cents integer default 0,
  paused_at timestamptz,
  pause_reason text,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index ix_runs_user_id on public.runs (user_id);

-- run_rows
create table public.run_rows (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references public.runs(id) on delete cascade,
  row_index integer not null,
  source_payload jsonb not null,
  business_id uuid references public.businesses(id),
  passes_completed integer not null default 0,
  passes_required integer not null default 1,
  status text not null default 'pending',
  error_reason text,
  created_at timestamptz not null default now(),
  unique (run_id, row_index)
);

-- verifications (APPEND-ONLY — triggers enforce)
-- NOTE: run_id has `on delete cascade` so test fixtures can clean up by deleting the
-- parent run. Application code does NOT issue raw deletes against runs in normal flow;
-- this cascade exists exclusively to enable test fixture teardown (the BEFORE DELETE
-- trigger on verifications fires on direct deletes but is bypassed by cascade only via
-- session_replication_role=replica — see test fixture pattern in Task 2).
create table public.verifications (
  id uuid primary key default gen_random_uuid(),
  business_id uuid references public.businesses(id),
  run_id uuid references public.runs(id) on delete cascade,
  row_index integer,
  pass integer not null default 1,
  method text not null,                  -- perplexity / firecrawl / cache / admin_edit / email_response / aggregator
  status text,                           -- active / likely_closed / closed / uncertain / errored
  confidence numeric(4,3),
  provenance jsonb default '{}'::jsonb,  -- CANON-08
  match_signals jsonb default '{}'::jsonb,
  evidence text,
  source_url text,
  cost_cents integer default 0,
  from_cache boolean default false,
  created_at timestamptz not null default now()
);
-- D-00-08 idempotency
alter table public.verifications
  add constraint uq_verifications_run_row_pass unique (run_id, row_index, pass);

-- api_calls (D-00-08; Phase 0 schema only; no calls until Phase 2)
create table public.api_calls (
  id uuid primary key default gen_random_uuid(),
  provider text not null,
  request_hash text not null,
  response_payload jsonb,
  cost_cents integer,
  created_at timestamptz not null default now(),
  constraint uq_api_calls_provider_hash unique (provider, request_hash)
);

-- app_config (D-00-05, D-00-10)
create table public.app_config (
  key text primary key,
  value jsonb not null,
  description text,
  updated_at timestamptz not null default now()
);

-- api_keys (admin-managed; Phase 0 schema only)
create table public.api_keys (
  id uuid primary key default gen_random_uuid(),
  provider text not null,                -- perplexity / firecrawl / resend
  label text,
  key_ciphertext text,                   -- encrypted at rest (pgcrypto), Phase 2 wires
  is_primary boolean default false,
  is_disabled boolean default false,
  monthly_cap_cents integer,
  low_balance_threshold_cents integer,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- budget_ledger (append-only spend; Phase 0 schema only)
create table public.budget_ledger (
  id bigserial primary key,
  api_key_id uuid references public.api_keys(id),
  event_type text not null,              -- estimate / charge / reconcile / cap_hit
  cents integer not null,
  running_total_cents integer,
  provider_truth_cents integer,
  meta jsonb default '{}'::jsonb,
  created_at timestamptz not null default now()
);

-- outreach_tickets (STUB for Phase 4; needed so audit trigger has a target)
create table public.outreach_tickets (
  id uuid primary key default gen_random_uuid(),
  run_id uuid references public.runs(id),
  status text not null default 'pending',
  token_hash text,
  approved_by uuid references auth.users(id),
  created_at timestamptz not null default now()
);

-- audit_log (D-00-06)
create table public.audit_log (
  id bigserial primary key,
  actor_user_id uuid references auth.users(id),
  action text not null,
  table_name text not null,
  row_pk text,
  before jsonb,
  after jsonb,
  diff jsonb,
  request_id text,
  created_at timestamptz not null default now()
);

-- worker_heartbeats (D-00-11 item 5)
create table public.worker_heartbeats (
  worker_id text primary key,
  last_seen_at timestamptz not null default now(),
  hostname text,
  version text
);
```

Normalize module shape (worker/workers/lib/normalize.py):
```python
def normalize_name(s: str) -> str: ...   # strip suffix (LLC/Inc/Corp), lowercase, strip punct
def normalize_domain(s: str) -> str: ...  # root domain, no scheme, no www, no path
def normalize_phone(s: str) -> str: ...   # E.164 US (+1XXXXXXXXXX)
def normalize_address(s: str) -> dict: ... # usaddress.tag() output (stub if usaddress not yet installed)
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Write all 7 SQL migrations and apply to dev Supabase</name>
  <files>supabase/config.toml, supabase/migrations/0001_init_schema.sql, supabase/migrations/0002_rls_policies.sql, supabase/migrations/0003_audit_log_trigger.sql, supabase/migrations/0004_verifications_append_only.sql, supabase/migrations/0005_pgmq_queues.sql, supabase/migrations/0006_app_config_seed.sql, supabase/migrations/0007_worker_heartbeats.sql</files>
  <read_first>
    - .planning/phases/00-foundation/00-CONTEXT.md (D-00-05 through D-00-10 — exact SQL shapes)
    - .planning/phases/00-foundation/00-RESEARCH.md (Pattern 2 lines 332-373, Pattern 3 lines 376-447, Pattern 4 lines 450-499, Pattern 5 lines 502-510)
    - .planning/research/ARCHITECTURE.md (Section 2 Component Inventory table at lines 130-152)
    - .planning/research/PITFALLS.md (P1 schema groundwork, P10 column allowlist, P11 pgmq vt, P12 Realtime opt-out)
  </read_first>
  <action>
    Initialize the Supabase project locally if not already:
    ```bash
    cd supabase  # create dir if missing
    # If config.toml does not exist, run: supabase init  (creates supabase/config.toml)
    ```
    If `supabase init` not feasible (no CLI in env), create a minimal `supabase/config.toml`:
    ```toml
    project_id = "ivmf-checker-dev"
    [db]
    major_version = 17
    ```

    Create the 7 migration files VERBATIM as shown below (paths exact). All migrations are idempotent where possible (`if not exists` / `create or replace`).

    **NOTE on idempotency:** `0001_init_schema.sql` uses bare `create table public.X (...)` (not `create table if not exists`). This is by design — a fresh dev project applies it once. Phase 0 polish backlog: TODO add `if not exists` to all `create table` statements in 0001 to support re-apply during demo workflows; deferred to Phase 0 polish PR (not this plan).

    **supabase/migrations/0001_init_schema.sql** — Use the full SQL from the `<interfaces>` block above. The 11 tables (businesses, runs, run_rows, verifications, api_calls, app_config, api_keys, budget_ledger, outreach_tickets, audit_log, worker_heartbeats) — copy each `create table` block exactly. **IMPORTANT:** the `verifications.run_id` FK MUST include `on delete cascade` (see `<interfaces>` block — required so test fixtures can clean up). Also enable required extensions at the top:
    ```sql
    create extension if not exists pgcrypto;
    create extension if not exists pg_trgm;
    create extension if not exists "uuid-ossp";
    -- pgmq is provisioned via Supabase Queues UI; do NOT create here.
    ```

    **supabase/migrations/0002_rls_policies.sql** — Enable RLS on every table created in 0001 and add baseline policies:
    ```sql
    alter table public.businesses enable row level security;
    alter table public.runs enable row level security;
    alter table public.run_rows enable row level security;
    alter table public.verifications enable row level security;
    alter table public.api_calls enable row level security;
    alter table public.app_config enable row level security;
    alter table public.api_keys enable row level security;
    alter table public.budget_ledger enable row level security;
    alter table public.outreach_tickets enable row level security;
    alter table public.audit_log enable row level security;
    alter table public.worker_heartbeats enable row level security;

    -- Baseline DENY for anon (defense in depth — Wave 3 adds user/admin policies)
    -- service_role bypasses RLS by default.

    -- Users can read their own runs (Wave 3 may extend)
    create policy runs_select_own on public.runs
      for select using (auth.uid() = user_id);

    -- Admin can do anything on app_config (Wave 3 wires role)
    create policy app_config_admin_all on public.app_config
      for all using ((auth.jwt() ->> 'role') = 'admin')
      with check ((auth.jwt() ->> 'role') = 'admin');

    -- Reads on app_config allowed for all authed users (allowlist must be readable to middleware via PostgREST too)
    create policy app_config_read on public.app_config
      for select using (auth.role() = 'authenticated' or auth.role() = 'anon');
      -- Note: middleware uses anon client to read allowlist; safe because value is non-sensitive

    -- audit_log: insert via trigger only; reads admin-only
    revoke insert, update, delete on public.audit_log from anon, authenticated;
    create policy audit_log_admin_read on public.audit_log
      for select using ((auth.jwt() ->> 'role') = 'admin');

    -- worker_heartbeats: service-role writes only; admin reads
    create policy worker_heartbeats_admin_read on public.worker_heartbeats
      for select using ((auth.jwt() ->> 'role') = 'admin');

    -- Pitfall P12 mitigation: do NOT add verifications/run_rows to supabase_realtime publication in Phase 0.
    ```

    **supabase/migrations/0003_audit_log_trigger.sql** — Use the EXACT SQL from RESEARCH.md Pattern 3 (lines 376-445). Copy the `audit_log_trigger()` function definition verbatim, then add the 4 trigger attachments (`trg_audit_app_config`, `trg_audit_api_keys`, `trg_audit_budget_ledger`, `trg_audit_outreach_tickets`).

    **supabase/migrations/0004_verifications_append_only.sql** — Use the EXACT SQL from RESEARCH.md Pattern 2 (lines 336-371). This file contains:
    ```sql
    create or replace function public.prevent_verifications_mutation()
    returns trigger
    language plpgsql
    as $$
    begin
      raise exception 'verifications is append-only — use INSERT with method=admin_edit'
        using errcode = 'P0001';
      return null;
    end;
    $$;

    create trigger trg_verifications_no_update
      before update on public.verifications
      for each row execute function public.prevent_verifications_mutation();

    create trigger trg_verifications_no_delete
      before delete on public.verifications
      for each row execute function public.prevent_verifications_mutation();
    ```
    The UNIQUE constraint on verifications and the api_calls table already shipped in 0001; this file is triggers only.

    Also REVOKE UPDATE/DELETE from all roles as belt-and-suspenders:
    ```sql
    revoke update, delete on public.verifications from anon, authenticated, service_role;
    ```

    **supabase/migrations/0005_pgmq_queues.sql** — D-00-09. pgmq extension is enabled via Supabase Queues GA in the dashboard; the migration is just queue creation:
    ```sql
    -- Requires the pgmq extension enabled in Supabase Dashboard → Database → Extensions → pgmq
    -- vt is configured at the consumer call site (D-00-09); pgmq.create() does NOT accept vt.
    select pgmq.create('q_verify');
    select pgmq.create('q_aggregator');
    ```

    **supabase/migrations/0006_app_config_seed.sql** — D-00-05 + D-00-10. Insert seed rows:
    ```sql
    insert into public.app_config (key, value, description) values
      ('email_domain_allowlist',
       '["syr.edu"]'::jsonb,
       'AUTH-02: domains allowed at sign-in. Admin can extend via UPDATE.'),
      ('column_allowlist',
       '["business_name","name","address","city","state","zip","owner","ein","phone","email","website","naics"]'::jsonb,
       'D-00-10: source-column headers permitted on upload. Defense against P10 PII leak.')
      on conflict (key) do nothing;

    -- D-00-05 RLS function
    create or replace function auth.is_allowed_domain(email text)
    returns boolean
    language sql
    stable
    security definer
    set search_path = public, auth
    as $$
      select exists (
        select 1
        from public.app_config
        where key = 'email_domain_allowlist'
          and value ?| array[ split_part(email, '@', 2) ]
      );
    $$;
    ```

    **supabase/migrations/0007_worker_heartbeats.sql** — Create this file containing exactly these two lines (no more, no less):
    ```sql
    -- placeholder; worker_heartbeats lives in 0001 because 0002 RLS policies reference it.
    select 1;
    ```
    Do NOT move worker_heartbeats out of 0001. The reason this placeholder exists: migrations apply in numeric order, so 0002 (which has `worker_heartbeats_admin_read` policy) MUST find the table already created by 0001. The 0007 file exists only so the file count matches research expectations.

    Apply all migrations to dev Supabase:
    ```bash
    # Option A: Supabase CLI (preferred)
    supabase link --project-ref <dev-project-ref>
    supabase db push

    # Option B: psql direct (if CLI not available)
    # IMPORTANT: SUPABASE_DEV_DB_URL MUST be the direct postgres-user connection string
    # (port 5432), NOT the pooler (port 6543). Test fixtures need postgres-user role to
    # bypass RLS and toggle session_replication_role; the pooler routes through a
    # different role and breaks these operations. See worker/.env.example.
    for f in supabase/migrations/*.sql; do
      psql "$SUPABASE_DEV_DB_URL" -f "$f"
    done
    ```
  </action>
  <verify>
    <automated>test -f supabase/migrations/0001_init_schema.sql && test -f supabase/migrations/0002_rls_policies.sql && test -f supabase/migrations/0003_audit_log_trigger.sql && test -f supabase/migrations/0004_verifications_append_only.sql && test -f supabase/migrations/0005_pgmq_queues.sql && test -f supabase/migrations/0006_app_config_seed.sql && test -f supabase/migrations/0007_worker_heartbeats.sql && grep -q "create table public.verifications" supabase/migrations/0001_init_schema.sql && grep -q "create table public.businesses" supabase/migrations/0001_init_schema.sql && grep -q "run_id uuid references public.runs(id) on delete cascade" supabase/migrations/0001_init_schema.sql && grep -q "uq_verifications_run_row_pass" supabase/migrations/0001_init_schema.sql && grep -q "uq_api_calls_provider_hash" supabase/migrations/0001_init_schema.sql && grep -q "prevent_verifications_mutation" supabase/migrations/0004_verifications_append_only.sql && grep -q "P0001" supabase/migrations/0004_verifications_append_only.sql && grep -q "audit_log_trigger" supabase/migrations/0003_audit_log_trigger.sql && grep -q "trg_audit_app_config" supabase/migrations/0003_audit_log_trigger.sql && grep -q "pgmq.create('q_verify')" supabase/migrations/0005_pgmq_queues.sql && grep -q "pgmq.create('q_aggregator')" supabase/migrations/0005_pgmq_queues.sql && grep -q "email_domain_allowlist" supabase/migrations/0006_app_config_seed.sql && grep -q "column_allowlist" supabase/migrations/0006_app_config_seed.sql && grep -q "is_allowed_domain" supabase/migrations/0006_app_config_seed.sql && grep -q "enable row level security" supabase/migrations/0002_rls_policies.sql && grep -q "placeholder" supabase/migrations/0007_worker_heartbeats.sql</automated>
  </verify>
  <acceptance_criteria>
    - All 7 migration files exist under `supabase/migrations/`
    - `0001_init_schema.sql` creates: businesses, runs, run_rows, verifications, api_calls, app_config, api_keys, budget_ledger, outreach_tickets, audit_log, worker_heartbeats (11 tables)
    - `0001` `verifications.run_id` FK INCLUDES `on delete cascade` (required for test fixture cleanup — verified by grep `run_id uuid references public.runs(id) on delete cascade`)
    - `0001` enables extensions: pgcrypto, pg_trgm, uuid-ossp
    - `0001` defines `uq_verifications_run_row_pass UNIQUE (run_id, row_index, pass)` AND `uq_api_calls_provider_hash UNIQUE (provider, request_hash)`
    - `0002_rls_policies.sql` calls `alter table … enable row level security` on every table from 0001 (11 ALTER statements)
    - `0003_audit_log_trigger.sql` defines `audit_log_trigger()` function AND attaches `trg_audit_app_config`, `trg_audit_api_keys`, `trg_audit_budget_ledger`, `trg_audit_outreach_tickets`
    - `0004_verifications_append_only.sql` contains `BEFORE UPDATE` + `BEFORE DELETE` triggers referencing `prevent_verifications_mutation()` AND raises `P0001` with message `'verifications is append-only — use INSERT with method=admin_edit'`
    - `0005_pgmq_queues.sql` contains both `pgmq.create('q_verify')` AND `pgmq.create('q_aggregator')` AND a comment noting vt is per-read (D-00-09)
    - `0006_app_config_seed.sql` inserts `email_domain_allowlist=["syr.edu"]` AND `column_allowlist=[...]` AND defines `auth.is_allowed_domain(email text)` function
    - `0007_worker_heartbeats.sql` contains exactly the placeholder comment + `select 1;` (no table creation, no other SQL)
    - After applying to dev: `psql $SUPABASE_DEV_DB_URL -tAc "select count(*) from information_schema.tables where table_schema='public'"` returns ≥ 11
    - After applying: `psql $SUPABASE_DEV_DB_URL -tAc "select count(*) from pgmq.meta where queue_name in ('q_verify','q_aggregator')"` returns 2
    - `psql $SUPABASE_DEV_DB_URL -tAc "select count(*) from public.app_config where key in ('email_domain_allowlist','column_allowlist')"` returns 2
  </acceptance_criteria>
  <done>All 7 migrations applied to the dev Supabase project; psql verification queries return expected counts; integration tests in Task 2/3 will execute successfully against the live schema.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Wire schema integration tests (replace xfail stubs with real assertions)</name>
  <files>worker/.env.example, worker/tests/conftest.py, worker/tests/test_schema.py, worker/tests/test_append_only.py, worker/tests/test_audit_trigger.py, worker/tests/test_pgmq.py, worker/tests/test_app_config.py, worker/tests/test_api_calls.py, worker/tests/test_verifications_schema.py, worker/tests/test_businesses_schema.py</files>
  <read_first>
    - worker/tests/conftest.py (existing fixture signatures from Wave 0)
    - worker/tests/test_append_only.py (current xfail stub from Wave 0)
    - supabase/migrations/0001_init_schema.sql (just created — column shapes, on-delete-cascade)
    - supabase/migrations/0004_verifications_append_only.sql (P0001 message)
    - .planning/phases/00-foundation/00-RESEARCH.md (Pattern 2 verification note at line 373)
  </read_first>
  <behavior>
    - test_schema.py: assert businesses, runs, run_rows, verifications, api_calls, app_config, api_keys, budget_ledger, audit_log, worker_heartbeats, outreach_tickets all exist in information_schema.tables
    - test_append_only.py::test_update_raises: insert a row, then UPDATE → psycopg.errors.RaiseException with SQLSTATE P0001
    - test_append_only.py::test_delete_raises: insert a row, then DELETE → P0001
    - test_append_only.py::test_unique_violation_run_row_pass: insert two rows with same (run_id, row_index, pass) → psycopg.errors.UniqueViolation (23505)
    - test_audit_trigger.py::test_app_config_update_writes_diff: UPDATE app_config, query latest audit_log row, assert diff jsonb not null and contains changed key
    - test_pgmq.py::test_queues_exist: query pgmq.meta, assert q_verify and q_aggregator both present
    - test_app_config.py::test_email_domain_allowlist_seeded: select value where key='email_domain_allowlist', assert 'syr.edu' in array
    - test_app_config.py::test_column_allowlist_seeded: select value where key='column_allowlist', assert non-empty array
    - test_app_config.py::test_is_allowed_domain_function: call auth.is_allowed_domain('a@syr.edu') → true; ('a@gmail.com') → false
    - test_api_calls.py::test_unique_violation: insert two api_calls with same (provider, request_hash) → 23505
    - test_verifications_schema.py::test_required_columns: introspect, assert columns id, business_id, run_id, row_index, pass, method, status, provenance, match_signals all present
    - test_businesses_schema.py::test_required_columns: introspect, assert columns id, name, normalized_name, ein, created_at present
  </behavior>
  <action>
    **Step A — update `worker/.env.example`** to document the connection-string requirement:
    Add or update this block (preserve existing content; add these lines if absent):
    ```
    # CRITICAL: SUPABASE_DEV_DB_URL MUST be the direct postgres-user connection string
    # (port 5432). The pooler URL (port 6543) routes through a non-postgres role that
    # cannot toggle session_replication_role or bypass RLS — test fixtures will fail.
    # Format: postgres://postgres:<PASSWORD>@db.<PROJECT>.supabase.co:5432/postgres
    SUPABASE_DEV_DB_URL=postgres://postgres:PASSWORD@db.YOUR_PROJECT.supabase.co:5432/postgres
    # Required for the test_user fixture to create an auth.users row via admin API.
    SUPABASE_URL=https://YOUR_PROJECT.supabase.co
    SUPABASE_SERVICE_ROLE_KEY=YOUR_SERVICE_ROLE_KEY
    ```

    **Step B — add a session-scoped `test_user` fixture and a `_role_guard` assertion** to `worker/tests/conftest.py`. APPEND this block (preserve existing fixtures):
    ```python
    # ---- Phase 0 schema-test fixtures (added in plan 02) ----
    import os
    import uuid
    import pytest

    @pytest.fixture(scope="session", autouse=True)
    def _role_guard(conn):
        """Fail loud if the test DB connection is not the postgres role.
        Required because schema tests must bypass RLS and toggle session_replication_role.
        Catches the 'pooler URL accidentally used' footgun."""
        with conn.cursor() as cur:
            cur.execute("select current_user")
            role = cur.fetchone()[0]
        assert role == "postgres", (
            f"Test connection must use postgres role; got {role!r}. "
            "Set SUPABASE_DEV_DB_URL to the direct port-5432 connection string, "
            "not the pooler (port 6543). See worker/.env.example."
        )

    @pytest.fixture(scope="session")
    def test_user_id(conn):
        """Create (or reuse) a stable test user in auth.users for FK targets.
        Uses a deterministic UUID so repeated runs converge on the same row.
        Inserts directly via service-role (bypasses RLS); avoids dependency on the
        Supabase admin REST API."""
        # Deterministic UUID derived from a namespace string — stable across runs.
        uid = uuid.UUID("00000000-0000-0000-0000-00000000beef")
        email = f"phase0-test-{uid}@syr.edu"
        with conn.cursor() as cur:
            # auth.users has many required columns in newer Supabase; insert minimal set
            # and let defaults fill the rest. instance_id default is the zero-UUID.
            cur.execute(
                """
                insert into auth.users (
                    id, instance_id, aud, role, email,
                    encrypted_password, email_confirmed_at,
                    raw_app_meta_data, raw_user_meta_data,
                    created_at, updated_at
                ) values (
                    %s,
                    '00000000-0000-0000-0000-000000000000',
                    'authenticated', 'authenticated', %s,
                    '', now(),
                    '{"role":"user"}'::jsonb, '{}'::jsonb,
                    now(), now()
                )
                on conflict (id) do nothing
                """,
                (str(uid), email),
            )
            conn.commit()
        return str(uid)
    ```

    **Step C — write each test file using the cascade-based cleanup pattern.** The canonical example (test_append_only.py — copy this style for the others that need fixtures):
    ```python
    """CANON-06 + CANON-07: verifications append-only + idempotency UNIQUE."""
    import uuid
    import pytest
    import psycopg

    pytestmark = pytest.mark.integration

    @pytest.fixture
    def seed_verification(conn, test_user_id):
        """Insert a verification row to UPDATE/DELETE against.
        Cleanup pattern: DELETE the parent run; verifications.run_id has
        `on delete cascade`. The BEFORE DELETE trigger on verifications fires
        for direct DELETEs but is bypassed during cascade only when
        session_replication_role='replica'. We set it for cleanup only."""
        run_id = uuid.uuid4()
        row_id = uuid.uuid4()
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into public.runs (id, user_id, status)
                values (%s, %s, 'pending')
                on conflict (id) do nothing
                """,
                (str(run_id), test_user_id),
            )
            cur.execute(
                """
                insert into public.verifications (id, run_id, row_index, pass, method)
                values (%s, %s, 0, 1, 'cache')
                returning id
                """,
                (str(row_id), str(run_id)),
            )
            vid = cur.fetchone()[0]
            conn.commit()
        try:
            yield vid, run_id
        finally:
            # Cleanup: bypass BEFORE DELETE trigger on verifications (which would
            # raise P0001 even via cascade) by setting session_replication_role.
            with conn.cursor() as cur:
                cur.execute("set session_replication_role = replica")
                cur.execute("delete from public.runs where id = %s", (str(run_id),))
                cur.execute("set session_replication_role = origin")
                conn.commit()

    def test_update_raises_p0001(conn, seed_verification):
        vid, _ = seed_verification
        with pytest.raises(psycopg.errors.RaiseException) as exc:
            with conn.cursor() as cur:
                cur.execute("update public.verifications set status='active' where id = %s", (vid,))
                conn.commit()
        assert exc.value.sqlstate == 'P0001'
        assert 'append-only' in str(exc.value)
        conn.rollback()

    def test_delete_raises_p0001(conn, seed_verification):
        vid, _ = seed_verification
        with pytest.raises(psycopg.errors.RaiseException) as exc:
            with conn.cursor() as cur:
                cur.execute("delete from public.verifications where id = %s", (vid,))
                conn.commit()
        assert exc.value.sqlstate == 'P0001'
        conn.rollback()

    def test_unique_violation_run_row_pass(conn, test_user_id):
        run_id = uuid.uuid4()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "insert into public.runs (id, user_id, status) values (%s, %s, 'pending')",
                    (str(run_id), test_user_id),
                )
                cur.execute(
                    "insert into public.verifications (run_id, row_index, pass, method) "
                    "values (%s, 0, 1, 'cache')",
                    (str(run_id),),
                )
                conn.commit()
                with pytest.raises(psycopg.errors.UniqueViolation) as exc:
                    cur.execute(
                        "insert into public.verifications (run_id, row_index, pass, method) "
                        "values (%s, 0, 1, 'cache')",
                        (str(run_id),),
                    )
                    conn.commit()
                assert exc.value.sqlstate == '23505'
            conn.rollback()
        finally:
            with conn.cursor() as cur:
                cur.execute("set session_replication_role = replica")
                cur.execute("delete from public.runs where id = %s", (str(run_id),))
                cur.execute("set session_replication_role = origin")
                conn.commit()
    ```

    Apply the same fixture-and-cleanup pattern to the other 7 files. Each must:
    1. Remove `@pytest.mark.xfail` and `raise NotImplementedError`
    2. Keep `pytestmark = pytest.mark.integration`
    3. Use the `conn` fixture from conftest.py AND `test_user_id` when inserting into runs
    4. Use `set session_replication_role = replica` to bypass verifications triggers during cleanup
    5. Wrap cleanup in `try/finally`

    For **test_audit_trigger.py** (no FK setup needed — app_config is pre-seeded):
    ```python
    def test_app_config_update_writes_diff(conn):
        with conn.cursor() as cur:
            cur.execute("""
                update public.app_config
                set description = 'test-update-' || extract(epoch from now())::text
                where key = 'email_domain_allowlist'
                returning updated_at
            """)
            conn.commit()
            cur.execute("""
                select diff, before, after
                from public.audit_log
                where table_name = 'app_config' and action = 'UPDATE'
                order by created_at desc limit 1
            """)
            row = cur.fetchone()
            assert row is not None, "no audit_log row after UPDATE"
            diff, before, after = row
            assert diff is not None, "diff jsonb is null"
            assert 'description' in diff, f"diff missing changed key: {diff}"
    ```

    For **test_pgmq.py**:
    ```python
    def test_queues_exist(conn):
        with conn.cursor() as cur:
            cur.execute("""
                select queue_name from pgmq.meta
                where queue_name in ('q_verify', 'q_aggregator')
            """)
            names = {r[0] for r in cur.fetchall()}
        assert names == {'q_verify', 'q_aggregator'}, f"queues missing: {names}"
    ```

    For **test_app_config.py**:
    ```python
    def test_email_domain_allowlist_seeded(conn):
        with conn.cursor() as cur:
            cur.execute("select value from public.app_config where key='email_domain_allowlist'")
            row = cur.fetchone()
            assert row is not None
            assert 'syr.edu' in row[0]

    def test_column_allowlist_seeded(conn):
        with conn.cursor() as cur:
            cur.execute("select value from public.app_config where key='column_allowlist'")
            row = cur.fetchone()
            assert row is not None and len(row[0]) > 5

    def test_is_allowed_domain_function(conn):
        with conn.cursor() as cur:
            cur.execute("select auth.is_allowed_domain('alice@syr.edu')")
            assert cur.fetchone()[0] is True
            cur.execute("select auth.is_allowed_domain('alice@gmail.com')")
            assert cur.fetchone()[0] is False
    ```

    For **test_verifications_schema.py** + **test_businesses_schema.py**: introspect `information_schema.columns` and assert column presence; example:
    ```python
    def test_required_columns(conn):
        required = {'id', 'business_id', 'run_id', 'row_index', 'pass', 'method', 'status', 'provenance', 'match_signals'}
        with conn.cursor() as cur:
            cur.execute("""
                select column_name from information_schema.columns
                where table_schema='public' and table_name='verifications'
            """)
            cols = {r[0] for r in cur.fetchall()}
        missing = required - cols
        assert not missing, f"verifications missing columns: {missing}"
    ```

    For **test_api_calls.py**: parallel to test_append_only.py::test_unique_violation but on api_calls (no FK to runs — simpler; no replication-role toggle needed for cleanup).

    For **test_schema.py**: introspect tables list and assert all 11 expected tables present.
  </action>
  <verify>
    <automated>cd worker && SUPABASE_DEV_DB_URL="${SUPABASE_DEV_DB_URL:-postgres://}" pytest tests/test_schema.py tests/test_append_only.py tests/test_audit_trigger.py tests/test_pgmq.py tests/test_app_config.py tests/test_api_calls.py tests/test_verifications_schema.py tests/test_businesses_schema.py -x --co 2>&1 | grep -c "::test_" | awk '{exit ($1 < 12)}' && ! grep -l "NotImplementedError\\|xfail" worker/tests/test_schema.py worker/tests/test_append_only.py worker/tests/test_audit_trigger.py worker/tests/test_pgmq.py worker/tests/test_app_config.py worker/tests/test_api_calls.py worker/tests/test_verifications_schema.py worker/tests/test_businesses_schema.py && grep -q "_role_guard\\|current_user" worker/tests/conftest.py && grep -q "test_user_id" worker/tests/conftest.py && grep -q "session_replication_role" worker/tests/test_append_only.py</automated>
  </verify>
  <acceptance_criteria>
    - `worker/.env.example` documents that SUPABASE_DEV_DB_URL must use port 5432 (postgres user, not pooler)
    - `worker/tests/conftest.py` contains a session-scoped `_role_guard` fixture that asserts `current_user = 'postgres'`
    - `worker/tests/conftest.py` contains a session-scoped `test_user_id` fixture that inserts (idempotently) a deterministic UUID into `auth.users`
    - All 8 listed test files no longer contain `@pytest.mark.xfail` or `NotImplementedError`
    - `pytest worker/tests/test_*.py --co -q` lists ≥ 12 test functions across these 8 files
    - Each file contains `pytestmark = pytest.mark.integration`
    - Tests that insert into `runs` use the `test_user_id` fixture (not `select id from auth.users limit 1`)
    - Tests that need to clean up after inserting into verifications use `set session_replication_role = replica` to bypass the BEFORE DELETE trigger, then reset to `origin`
    - When run against the migrated dev DB: `cd worker && pytest tests/test_append_only.py tests/test_pgmq.py tests/test_app_config.py -x` exits 0
    - test_append_only.py contains `psycopg.errors.RaiseException` AND assertion on `sqlstate == 'P0001'`
    - test_audit_trigger.py asserts `diff is not None` AND checks for a changed key in the diff jsonb
  </acceptance_criteria>
  <done>Six of ten phase requirements (CANON-05, CANON-06, CANON-07, CANON-08, AUTH-04) have green integration tests against the live schema. Append-only contract is provably enforced. Idempotency UNIQUEs reject duplicates. Test fixtures use a stable test user and clean up via cascade + replica role.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Normalize helper module + unit tests (CANON-03)</name>
  <files>worker/workers/__init__.py, worker/workers/lib/__init__.py, worker/workers/lib/normalize.py, worker/tests/test_normalize.py</files>
  <read_first>
    - worker/tests/test_normalize.py (current xfail stub from Wave 0)
    - .planning/REQUIREMENTS.md (CANON-03 exact wording)
    - .planning/phases/00-foundation/00-RESEARCH.md (Phase Requirements row CANON-03 at line 66)
  </read_first>
  <behavior>
    Test cases (must all pass):
    - normalize_name("Acme Corp, LLC") == "acme corp"
    - normalize_name("Acme Corp.") == "acme corp"
    - normalize_name("ACME CORPORATION") == "acme"
    - normalize_name("  Café  Resto  ") == "café resto"   (Unicode preserved, whitespace collapsed)
    - normalize_name("") == ""
    - normalize_domain("https://www.example.com/path") == "example.com"
    - normalize_domain("HTTP://Sub.Example.COM") == "sub.example.com"
    - normalize_domain("example.com/foo") == "example.com"
    - normalize_domain("") == ""
    - normalize_phone("(315) 443-1234") == "+13154431234"
    - normalize_phone("315.443.1234") == "+13154431234"
    - normalize_phone("1-315-443-1234") == "+13154431234"
    - normalize_phone("+13154431234") == "+13154431234"
    - normalize_phone("invalid") returns None or raises ValueError (document behavior)
    - normalize_address("123 Main St, Syracuse, NY 13210") returns dict with street_address, city, state, zip keys (stub uses regex split; usaddress is a Phase 1 add-on per STACK.md)
  </behavior>
  <action>
    Create `worker/workers/__init__.py` (empty).
    Create `worker/workers/lib/__init__.py` (empty).

    Create `worker/workers/lib/normalize.py`:
    ```python
    """CANON-03: Normalize name, domain, phone, address before canonical matching.

    These helpers are imported by Phase 1 canonical matching logic.
    Phase 0 ships and tests them; Phase 1 wires them into the 2-of-N flow.
    """
    from __future__ import annotations
    import re
    from typing import Optional

    # Suffixes stripped from business names before matching.
    _NAME_SUFFIXES = (
        " llc", " l.l.c.", " l.l.c", " inc", " inc.",
        " incorporated", " corp", " corp.", " corporation",
        " co", " co.", " company", " ltd", " ltd.", " limited",
        " lp", " l.p.", " llp", " l.l.p.", " pllc", " p.l.l.c.",
    )

    _PUNCT_RX = re.compile(r"[,.;:!?\"'`()\[\]{}]")
    _WS_RX = re.compile(r"\s+")
    _PHONE_DIGITS_RX = re.compile(r"\D+")
    _DOMAIN_SCHEME_RX = re.compile(r"^[a-z]+://", re.IGNORECASE)


    def normalize_name(s: str) -> str:
        """Strip suffixes, lowercase, collapse whitespace. Unicode preserved."""
        if not s:
            return ""
        x = s.strip().lower()
        x = _PUNCT_RX.sub("", x)
        x = _WS_RX.sub(" ", x).strip()
        for suf in _NAME_SUFFIXES:
            if x.endswith(suf):
                x = x[: -len(suf)].rstrip()
                break
        # Handle suffix that's the only word ("Corporation" alone)
        if x.split()[-1:] in ([s.strip() for s in ["corporation", "incorporated", "company"]],):
            x = " ".join(x.split()[:-1])
        return x.strip()


    def normalize_domain(s: str) -> str:
        """Strip scheme, www., path. Return lowercase root domain."""
        if not s:
            return ""
        x = s.strip().lower()
        x = _DOMAIN_SCHEME_RX.sub("", x)
        # strip path
        x = x.split("/", 1)[0]
        # strip leading www.
        if x.startswith("www."):
            x = x[4:]
        return x


    def normalize_phone(s: str) -> Optional[str]:
        """Return E.164 US format (+1XXXXXXXXXX) or None if not parseable."""
        if not s:
            return None
        digits = _PHONE_DIGITS_RX.sub("", s)
        if len(digits) == 10:
            return f"+1{digits}"
        if len(digits) == 11 and digits.startswith("1"):
            return f"+{digits}"
        return None


    def normalize_address(s: str) -> dict:
        """Phase 0 stub: regex split into components.
        Phase 1 will replace with usaddress.tag() per STACK.md.
        """
        if not s:
            return {}
        # Best-effort: "123 Main St, Syracuse, NY 13210"
        parts = [p.strip() for p in s.split(",")]
        out: dict = {"raw": s.strip()}
        if len(parts) >= 1:
            out["street_address"] = parts[0]
        if len(parts) >= 2:
            out["city"] = parts[1]
        if len(parts) >= 3:
            # "NY 13210"
            tokens = parts[2].split()
            if tokens:
                out["state"] = tokens[0]
                if len(tokens) > 1:
                    out["zip"] = tokens[1]
        return out
    ```

    Replace `worker/tests/test_normalize.py` with real test cases (no xfail):
    ```python
    """CANON-03 unit tests for normalize helpers."""
    import pytest
    from workers.lib.normalize import (
        normalize_name, normalize_domain, normalize_phone, normalize_address,
    )

    @pytest.mark.parametrize("raw,expected", [
        ("Acme Corp, LLC", "acme corp"),
        ("Acme Corp.", "acme corp"),
        ("ACME CORPORATION", "acme"),
        ("  Café  Resto  ", "café resto"),
        ("", ""),
    ])
    def test_normalize_name(raw, expected):
        assert normalize_name(raw) == expected

    @pytest.mark.parametrize("raw,expected", [
        ("https://www.example.com/path", "example.com"),
        ("HTTP://Sub.Example.COM", "sub.example.com"),
        ("example.com/foo", "example.com"),
        ("", ""),
    ])
    def test_normalize_domain(raw, expected):
        assert normalize_domain(raw) == expected

    @pytest.mark.parametrize("raw,expected", [
        ("(315) 443-1234", "+13154431234"),
        ("315.443.1234", "+13154431234"),
        ("1-315-443-1234", "+13154431234"),
        ("+13154431234", "+13154431234"),
    ])
    def test_normalize_phone_e164(raw, expected):
        assert normalize_phone(raw) == expected

    def test_normalize_phone_invalid_returns_none():
        assert normalize_phone("invalid") is None
        assert normalize_phone("") is None

    def test_normalize_address_basic():
        result = normalize_address("123 Main St, Syracuse, NY 13210")
        assert result["street_address"] == "123 Main St"
        assert result["city"] == "Syracuse"
        assert result["state"] == "NY"
        assert result["zip"] == "13210"

    def test_normalize_address_empty():
        assert normalize_address("") == {}
    ```

    The test imports `from workers.lib.normalize import ...` — this requires the worker directory to be on Python path. Add to `worker/pyproject.toml` (if not already):
    ```toml
    [tool.pytest.ini_options]
    testpaths = ["tests"]
    pythonpath = ["."]   # makes `workers` package importable from tests/
    addopts = "-x -ra --strict-markers"
    ```
    Update the existing pyproject.toml from Wave 0 with the `pythonpath = ["."]` line.
  </action>
  <verify>
    <automated>cd worker && python -c "from workers.lib.normalize import normalize_name, normalize_domain, normalize_phone, normalize_address; assert normalize_name('Acme Corp, LLC') == 'acme corp'; assert normalize_domain('https://www.example.com/x') == 'example.com'; assert normalize_phone('(315) 443-1234') == '+13154431234'; print('OK')" && cd worker && pytest tests/test_normalize.py -x</automated>
  </verify>
  <acceptance_criteria>
    - `worker/workers/__init__.py` and `worker/workers/lib/__init__.py` exist (empty acceptable)
    - `worker/workers/lib/normalize.py` defines `normalize_name`, `normalize_domain`, `normalize_phone`, `normalize_address`
    - All 4 functions importable: `python -c "from workers.lib.normalize import normalize_name, normalize_domain, normalize_phone, normalize_address"` exits 0
    - `worker/tests/test_normalize.py` no longer contains `@pytest.mark.xfail`
    - `cd worker && pytest tests/test_normalize.py -x` exits 0 with at least 11 tests passing (5 name + 4 domain + 4 phone + 1 phone-invalid + 2 address)
    - `normalize_phone("(315) 443-1234")` returns exactly `"+13154431234"` (E.164)
    - `normalize_domain("https://www.example.com/path")` returns exactly `"example.com"`
    - `worker/pyproject.toml` contains `pythonpath = ["."]` so tests can import the workers package
  </acceptance_criteria>
  <done>CANON-03 ships as a tested helper module. Phase 1 canonical matching will import these helpers unchanged.</done>
</task>

</tasks>

<verification>
- `psql $SUPABASE_DEV_DB_URL -tAc "select count(*) from information_schema.tables where table_schema='public'"` returns ≥ 11.
- `psql $SUPABASE_DEV_DB_URL -tAc "select count(*) from pgmq.meta"` returns ≥ 2.
- `cd worker && pytest tests/test_schema.py tests/test_append_only.py tests/test_audit_trigger.py tests/test_pgmq.py tests/test_app_config.py tests/test_api_calls.py tests/test_verifications_schema.py tests/test_businesses_schema.py tests/test_normalize.py -x` exits 0 (≥ 19 tests passing).
- 6 of 10 phase requirements now have green tests.
</verification>

<success_criteria>
- D-00-11 item 4 (append-only + idempotency) is locally verifiable: `psql` UPDATE raises P0001; duplicate INSERT raises 23505.
- The schema gate is green: every subsequent wave can introspect the dev DB and find the expected shape.
- CANON-03 normalize helpers ship and are unit-tested.
- AUTH-04 audit-log trigger is provably writing diff jsonb on app_config UPDATE.
</success_criteria>

<output>
After completion, create `.planning/phases/00-foundation/00-02-supabase-schema-rls-SUMMARY.md` documenting:
- Migration order and any deviations from research patterns
- Test fixture cleanup pattern: cascade DELETE on runs + `session_replication_role=replica` to bypass verifications BEFORE DELETE trigger
- The `test_user_id` deterministic-UUID fixture and why direct `auth.users` insert (not Supabase admin API) was chosen
- Decision: `worker_heartbeats` table lives in `0001_init_schema.sql` (referenced by 0002 RLS policies); `0007_worker_heartbeats.sql` is a placeholder no-op
- TODO: make 0001_init_schema.sql idempotent (`create table if not exists`) in a Phase 0 polish PR — needed so demo workflows can re-apply
- Requirements closed: CANON-03, CANON-05, CANON-06, CANON-07, CANON-08, AUTH-04
</output>
</content>
</invoke>