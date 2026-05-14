-- Phase 0 / Plan 02 — generic audit log trigger (D-00-06, AUTH-04).
-- One function reused across all admin-writable tables.

create or replace function public.audit_log_trigger()
returns trigger
language plpgsql
security definer
as $$
declare
  v_before jsonb;
  v_after  jsonb;
  v_diff   jsonb;
  v_pk     text;
begin
  v_before := case when TG_OP in ('UPDATE','DELETE') then to_jsonb(OLD) else null end;
  v_after  := case when TG_OP in ('INSERT','UPDATE') then to_jsonb(NEW) else null end;

  if TG_OP = 'UPDATE' then
    select jsonb_object_agg(key, v_after -> key)
      into v_diff
      from jsonb_each(v_after)
     where v_before -> key is distinct from v_after -> key;
  end if;

  v_pk := coalesce(
    (v_after  ->> 'id'),
    (v_before ->> 'id'),
    (v_after  ->> 'key'),     -- app_config keyed by 'key'
    (v_before ->> 'key')
  );

  insert into public.audit_log
    (actor_user_id, action, table_name, row_pk, before, after, diff, request_id)
  values
    (auth.uid(), TG_OP, TG_TABLE_NAME, v_pk, v_before, v_after, v_diff,
     current_setting('app.request_id', true));

  return coalesce(NEW, OLD);
end;
$$;

-- Attach to admin-writable tables (D-00-06)
create trigger trg_audit_app_config
  after insert or update or delete on public.app_config
  for each row execute function public.audit_log_trigger();

create trigger trg_audit_api_keys
  after insert or update or delete on public.api_keys
  for each row execute function public.audit_log_trigger();

create trigger trg_audit_budget_ledger
  after insert or update or delete on public.budget_ledger
  for each row execute function public.audit_log_trigger();

create trigger trg_audit_outreach_tickets
  after insert or update or delete on public.outreach_tickets
  for each row execute function public.audit_log_trigger();
