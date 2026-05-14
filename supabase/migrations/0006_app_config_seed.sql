-- Phase 0 / Plan 02 — app_config seed rows + domain allowlist RLS function
-- (D-00-05, D-00-10, AUTH-02).

insert into public.app_config (key, value, description) values
  ('email_domain_allowlist',
   '["syr.edu"]'::jsonb,
   'AUTH-02: domains allowed at sign-in. Admin can extend via UPDATE.'),
  ('column_allowlist',
   '["business_name","name","address","city","state","zip","owner","ein","phone","email","website","naics"]'::jsonb,
   'D-00-10: source-column headers permitted on upload. Defense against P10 PII leak.')
  on conflict (key) do nothing;

-- D-00-05 — RLS-callable function that reads the allowlist row.
-- security definer + fixed search_path so it can be called by any role without
-- granting them direct SELECT on app_config.
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
