-- Phase 0 / Plan 02 — RLS policies (D-00-05, AUTH-02, AUTH-04).
-- Enable RLS on every table from 0001. Baseline policies; Wave 3 adds per-role detail.
-- service_role bypasses RLS by default.

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

-- Users can read their own runs (Wave 3 may extend with more policies)
create policy runs_select_own on public.runs
  for select using (auth.uid() = user_id);

-- Admin can do anything on app_config (Wave 3 wires role)
create policy app_config_admin_all on public.app_config
  for all using ((auth.jwt() ->> 'role') = 'admin')
  with check ((auth.jwt() ->> 'role') = 'admin');

-- Reads on app_config allowed for all authed (and anon) users.
-- NOTE: middleware uses anon client to read allowlist; safe because the value is
-- non-sensitive (allowed sign-in domains).
create policy app_config_read on public.app_config
  for select using (auth.role() = 'authenticated' or auth.role() = 'anon');

-- audit_log: insert via trigger only; reads admin-only
revoke insert, update, delete on public.audit_log from anon, authenticated;
create policy audit_log_admin_read on public.audit_log
  for select using ((auth.jwt() ->> 'role') = 'admin');

-- worker_heartbeats: service-role writes only; admin reads
create policy worker_heartbeats_admin_read on public.worker_heartbeats
  for select using ((auth.jwt() ->> 'role') = 'admin');

-- Pitfall P12 mitigation: do NOT add verifications/run_rows to supabase_realtime
-- publication in Phase 0. Phase 1+ will add Realtime with matching RLS policies.
