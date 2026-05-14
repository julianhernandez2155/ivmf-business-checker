-- Phase 0 / Plan 02 — verifications is append-only (D-00-07, CANON-06).
-- BEFORE UPDATE/DELETE triggers raise unconditionally. Not even service-role bypasses.
-- The UNIQUE constraint shipped in 0001; this file is triggers + revoke only.

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

-- Belt-and-suspenders: revoke UPDATE/DELETE privileges from all roles.
-- The triggers above are the unbypassable guard; this is defense in depth so
-- privilege checks fail BEFORE the trigger fires.
revoke update, delete on public.verifications from anon, authenticated, service_role;
