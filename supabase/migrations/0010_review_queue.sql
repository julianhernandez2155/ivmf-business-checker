-- Phase 0 / Plan 08 — review_queue table (GAP-5 closure; tracked by 00-08 executor).
--
-- Closes Codex peer review GAP-5 (MEDIUM) recorded in
-- .planning/phases/00-foundation/00-VERIFICATION.md:
--
--   ROADMAP Phase 1 acceptance criterion 2 ("Rows hitting 2-of-N consensus ...
--   are routed to the admin review queue") requires a `review_queue` table.
--   None existed in 0001..0008. Landing here in Phase 0 gap closure avoids
--   regenerating the codegen baselines (web/db/schema.ts +
--   worker/workers/lib/models.py) twice (once for this table, once for Phase 1).
--
-- Downstream consumers:
--   - Phase 1 acceptance criterion 2 (CANON-02: 2-of-N consensus routing)
--   - Phase 3 MANUAL-01 (unified review queue UI)
--   - Phase 3 MANUAL-02 (admin resolution writes)
--
-- AUTH-04 coverage:
--   The generic public.audit_log_trigger() from migration 0003 is attached so
--   every INSERT / UPDATE / DELETE on review_queue produces an audit_log row.
--   This extends AUTH-04 ("audit log with before/after diff on every admin
--   write") to the queue table without per-table trigger code (D-00-06 reuse).
--
-- Decision invariants honored:
--   D-00-03: new sequential migration applied via Supabase CLI (no Drizzle).
--   D-00-05: admin RLS policies use defense-in-depth — both
--            auth.current_role_claim() = 'admin' AND auth.is_allowed_domain(email).
--            Mirrors the GAP-2 fix shape from Plan 00-07's 0009 migration.
--   D-00-06: reuse generic audit_log_trigger() rather than per-table function.
--
-- Re-applicability:
--   - `create table` (matches 0001 convention; idempotent re-apply is a Phase 0
--     polish backlog item per STATE.md Anti-Patterns Found item 2).
--   - All triggers + policies use `drop ... if exists` so retry-after-table-error
--     is graceful.

-- ─── Table ────────────────────────────────────────────────────────────────────
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
  -- kind is an enum-like check constraint; CHECK (not Postgres ENUM type) so
  -- adding values is a simple ALTER instead of a multi-step ALTER TYPE that
  -- dev/prod can drift on. Matches the convention in 0001 (`runs.status text`).
  constraint chk_review_queue_kind
    check (kind in ('canonical_merge', 'uncertain', 'outreach_response')),
  constraint chk_review_queue_status
    check (status in ('open', 'resolved', 'dismissed')),
  -- Resolution-shape invariant: open rows have no resolution metadata; resolved
  -- and dismissed rows must record at least when they were resolved. Keeps the
  -- Phase 3 MANUAL-02 admin-resolution UI honest.
  constraint chk_review_queue_resolution_shape
    check (
      (status = 'open' and resolved_at is null and resolved_by is null and resolution is null)
      or (status <> 'open' and resolved_at is not null)
    )
);

-- ─── Indexes ──────────────────────────────────────────────────────────────────
-- Partial index on the hot path (Phase 3 MANUAL-01 queries open-queue UI on
-- every load). Resolved/dismissed rows accumulate but stay out of the index.
create index ix_review_queue_status_kind
  on public.review_queue (status, kind)
  where status = 'open';

-- Lookup index for "what did this admin file" audit views.
create index ix_review_queue_created_by
  on public.review_queue (created_by)
  where created_by is not null;

-- ─── RLS ──────────────────────────────────────────────────────────────────────
alter table public.review_queue enable row level security;

-- Admin-only read. Defense-in-depth: current_role_claim AND is_allowed_domain
-- (mirrors the GAP-2 fix shape — see Plan 00-07's 0009_auth_fixes.sql).
-- auth.current_role_claim() exists from migration 0008 (rewritten body in 0009).
-- auth.is_allowed_domain() exists from migration 0006.
drop policy if exists review_queue_admin_read on public.review_queue;
create policy review_queue_admin_read on public.review_queue
  for select
  using (
    auth.current_role_claim() = 'admin'
    and auth.is_allowed_domain(auth.email())
  );

-- Admin-only write (UPDATE for resolution; DELETE not expected but covered).
-- INSERTs in normal operation flow through service_role (worker writes when
-- 2-of-N consensus fires in Phase 1), which bypasses RLS by default.
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

-- service_role bypasses RLS by default; Phase 1 worker INSERTs queue items via
-- service-role when the 2-of-N consensus fires. No additional grant needed.

-- ─── Audit trigger attachment (D-00-06, AUTH-04 extension) ────────────────────
-- Verbatim idiom from 0003. Every INSERT/UPDATE/DELETE on review_queue writes
-- a row to public.audit_log via the generic trigger function.
drop trigger if exists trg_audit_review_queue on public.review_queue;
create trigger trg_audit_review_queue
  after insert or update or delete on public.review_queue
  for each row execute function public.audit_log_trigger();

comment on table public.review_queue is
  'GAP-5 fix (.planning/phases/00-foundation/00-VERIFICATION.md): consumed by Phase 1 acceptance criterion 2 + Phase 3 MANUAL-01/02.';
