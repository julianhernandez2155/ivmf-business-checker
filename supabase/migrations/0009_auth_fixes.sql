-- Phase 0 / Plan 07 — Codex peer review gap closure (GAP-1 HIGH + GAP-2 HIGH).
-- See .planning/phases/00-foundation/00-VERIFICATION.md §Codex Peer Review Gaps.
-- Plan source: .planning/phases/00-foundation/00-07-rbac-allowlist-fixes-PLAN.md
--
-- ---------------------------------------------------------------------------
-- GAP-1 (HIGH): admin RBAC helper ordering inverted.
--   File:    supabase/migrations/0008_rbac_role_default.sql:45
--   Symptom: auth.current_role_claim() reads `auth.jwt() ->> 'role'` FIRST,
--            which in Supabase returns the Postgres role claim
--            (`authenticated` / `anon` / `service_role`), never the custom
--            `admin`. Falls through to `app_metadata.role` ONLY if the JWT role
--            is null. Result: app_config_admin_all policy never grants admin
--            access — no user is functionally an admin.
--   Fix:     Reorder so `app_metadata.role` is read first; drop the reserved
--            `role` claim from the coalesce chain entirely; add `user_role` as
--            a non-reserved escape hatch for tests / non-standard JWTs.
--
-- GAP-2 (HIGH): domain allowlist not enforced by RLS policies.
--   File:    supabase/migrations/0002_rls_policies.sql (multiple policies) +
--            helper at 0006_app_config_seed.sql:auth.is_allowed_domain()
--   Symptom: The helper function auth.is_allowed_domain(email) exists but NO
--            RLS policy actually calls it. Middleware blocks non-allowlisted
--            domains at the browser route layer, but a JWT-bearing client
--            hitting Supabase REST directly bypasses the domain gate entirely.
--   Fix:     Add `AND auth.is_allowed_domain(auth.email())` to every
--            user-facing and admin RLS policy. Use DROP POLICY IF EXISTS +
--            CREATE POLICY (Postgres < 15 has no ALTER POLICY for predicates).
--
-- Honors D-00-05 (defense-in-depth allowlist must be enforced at BOTH the
-- middleware layer AND the data layer) and D-00-03 (Supabase CLI migrations
-- are the single source of truth — never amend 0001..0008, always add a new
-- sequential migration).
-- ---------------------------------------------------------------------------


-- ============================================================================
-- GAP-1 FIX: rewrite auth.current_role_claim()
-- ============================================================================

create or replace function auth.current_role_claim()
returns text
language sql
stable
as $$
  -- GAP-1 fix: read app_metadata.role FIRST. The top-level 'role' JWT claim
  -- is Supabase's Postgres role (authenticated/anon/service_role) and will
  -- NEVER be 'admin'. Falling back to it as a primary source guaranteed that
  -- no user could be functionally admin. See 0008 (original) and
  -- .planning/phases/00-foundation/00-VERIFICATION.md GAP-1.
  select coalesce(
    nullif((auth.jwt() -> 'app_metadata' ->> 'role'), ''),
    nullif(auth.jwt() ->> 'user_role', ''),  -- non-reserved escape hatch for tests / non-standard JWTs
    'user'
  );
$$;

comment on function auth.current_role_claim() is
  'GAP-1 fix (.planning/phases/00-foundation/00-VERIFICATION.md): reads app_metadata.role first. '
  'The top-level JWT role claim is Supabase Postgres role (authenticated/anon/service_role) — '
  'never admin — so the original 0008 ordering meant no user could be functionally admin.';


-- ============================================================================
-- GAP-2 FIX: add auth.is_allowed_domain(auth.email()) to every user-facing
-- and admin RLS policy from 0002 (plus the 0008 rewrite of app_config_admin_all).
--
-- Postgres < 15 has no ALTER POLICY for predicate changes — we DROP and CREATE.
-- All operations are idempotent (DROP IF EXISTS) so the migration is re-runnable.
-- ============================================================================

-- ----- runs_select_own --------------------------------------------------
-- Original (0002): for select using (auth.uid() = user_id)
-- GAP-2: a JWT-bearing client whose auth.uid()=user_id but whose email is
-- @gmail.com (or any non-allowlisted domain) can SELECT their own runs via
-- Supabase REST, bypassing the middleware-only domain gate entirely.
drop policy if exists runs_select_own on public.runs;
create policy runs_select_own on public.runs
  for select
  using (
    auth.uid() = user_id
    and auth.is_allowed_domain(auth.email())
  );

comment on policy runs_select_own on public.runs is
  'GAP-2 fix: conjunctive allowlist + ownership. Defense-in-depth at the data layer (D-00-05).';


-- ----- app_config_read --------------------------------------------------
-- Original (0002): for select using (auth.role() = 'authenticated' or auth.role() = 'anon')
-- GAP-2 + D-00-05: authenticated users must additionally pass the allowlist;
-- anon retains read access (middleware needs to bootstrap the allowlist itself
-- before a user has a session — the value is non-sensitive per 0002 note).
drop policy if exists app_config_read on public.app_config;
create policy app_config_read on public.app_config
  for select
  using (
    (auth.role() = 'authenticated' and auth.is_allowed_domain(auth.email()))
    or auth.role() = 'anon'
  );

comment on policy app_config_read on public.app_config is
  'GAP-2 fix: authenticated reads gated by allowlist. anon read preserved so middleware can '
  'bootstrap the allowlist itself before sign-in (D-00-05 carve-out — value is non-sensitive).';


-- ----- app_config_admin_all ---------------------------------------------
-- Original (0008): for all using/with check (auth.current_role_claim() = 'admin')
-- GAP-2: an `app_metadata.role='admin'` accidentally flipped onto a user with a
-- non-allowlisted domain would be a privilege escalation path. Admin must ALSO
-- be on an allowlisted domain — defense-in-depth.
drop policy if exists app_config_admin_all on public.app_config;
create policy app_config_admin_all on public.app_config
  for all
  using (
    auth.current_role_claim() = 'admin'
    and auth.is_allowed_domain(auth.email())
  )
  with check (
    auth.current_role_claim() = 'admin'
    and auth.is_allowed_domain(auth.email())
  );

comment on policy app_config_admin_all on public.app_config is
  'GAP-1 + GAP-2 fix: admin claim from app_metadata.role (via current_role_claim) AND '
  'allowlisted domain. Closes the role-flip-to-non-allowlisted-user escalation path.';


-- ----- audit_log_admin_read ---------------------------------------------
-- Original (0002): for select using ((auth.jwt() ->> 'role') = 'admin')
-- GAP-1: that predicate could NEVER be true (top-level role is the Postgres
-- role). Rewrite via current_role_claim() helper, AND gate on allowlist.
drop policy if exists audit_log_admin_read on public.audit_log;
create policy audit_log_admin_read on public.audit_log
  for select
  using (
    auth.current_role_claim() = 'admin'
    and auth.is_allowed_domain(auth.email())
  );

comment on policy audit_log_admin_read on public.audit_log is
  'GAP-1 + GAP-2 fix: admin via current_role_claim (app_metadata.role) AND allowlisted domain.';


-- ----- worker_heartbeats_admin_read -------------------------------------
-- Original (0002): for select using ((auth.jwt() ->> 'role') = 'admin')
-- Same broken predicate as audit_log_admin_read; same fix.
drop policy if exists worker_heartbeats_admin_read on public.worker_heartbeats;
create policy worker_heartbeats_admin_read on public.worker_heartbeats
  for select
  using (
    auth.current_role_claim() = 'admin'
    and auth.is_allowed_domain(auth.email())
  );

comment on policy worker_heartbeats_admin_read on public.worker_heartbeats is
  'GAP-1 + GAP-2 fix: admin via current_role_claim (app_metadata.role) AND allowlisted domain.';


-- ============================================================================
-- Tables NOT touched by this migration (intentional):
--
-- run_rows, verifications, api_calls, businesses, api_keys, budget_ledger,
-- outreach_tickets — these have RLS ENABLED in 0002 but NO user-facing
-- SELECT/INSERT/UPDATE policy. Default deny applies. Phase 1 will add policies
-- for these tables AND must include auth.is_allowed_domain(auth.email()) in
-- every USING/WITH CHECK clause per D-00-05.
--
-- The Codex GAP-2 finding specifically targets policies that EXIST and bypass
-- the allowlist; this migration does not invent new policies, only patches the
-- broken ones.
-- ============================================================================
