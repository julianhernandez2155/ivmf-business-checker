-- Phase 0 / Plan 04 — AUTH-03 RBAC role default + JWT claim helper.
-- Closes AUTH-03: two-role RBAC (admin / user) via app_metadata.role.
--
-- Three pieces:
--   1. After-insert trigger on auth.users sets raw_app_meta_data.role = 'user'
--      when not already supplied (admin promotion is a service-role UPDATE).
--   2. auth.current_role_claim() — RLS helper that extracts role from the JWT.
--   3. Replace app_config_admin_all policy to use current_role_claim() so
--      admin promotion via app_metadata propagates straight into RLS.

-- 1) Trigger: default role='user' on new auth.users
create or replace function public.handle_new_user_role()
returns trigger
language plpgsql
security definer
set search_path = public, auth
as $$
begin
  -- Only set if role is not already present (allows manual provisioning).
  if NEW.raw_app_meta_data is null
     or (NEW.raw_app_meta_data ? 'role') = false then
    update auth.users
      set raw_app_meta_data = coalesce(NEW.raw_app_meta_data, '{}'::jsonb)
                             || jsonb_build_object('role', 'user')
      where id = NEW.id;
  end if;
  return NEW;
end;
$$;

drop trigger if exists trg_handle_new_user_role on auth.users;
create trigger trg_handle_new_user_role
  after insert on auth.users
  for each row execute function public.handle_new_user_role();

-- 2) RLS helper — extract role from JWT claims with sensible fallback.
-- Reads the standard `role` claim first (some Supabase configs put it there)
-- then `app_metadata.role` (canonical home for Supabase Auth custom claims),
-- defaulting to 'user' so policies stay deny-by-default for unknown roles.
create or replace function auth.current_role_claim()
returns text
language sql
stable
as $$
  select coalesce(
    nullif(auth.jwt() ->> 'role', ''),
    nullif((auth.jwt() -> 'app_metadata' ->> 'role'), ''),
    'user'
  );
$$;

-- 3) Update the app_config admin policy from 0002 to use the helper.
-- The previous policy in 0002 checked raw_app_meta_data via a different shape;
-- this version reads the same source through the JWT helper so middleware AND
-- RLS read role from the SAME canonical path (app_metadata.role).
drop policy if exists app_config_admin_all on public.app_config;
create policy app_config_admin_all on public.app_config
  for all
  using (auth.current_role_claim() = 'admin')
  with check (auth.current_role_claim() = 'admin');
