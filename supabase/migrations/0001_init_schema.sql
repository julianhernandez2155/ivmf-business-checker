-- Phase 0 / Plan 02 — initial schema (D-00-05..D-00-10).
-- 11 tables: businesses, runs, run_rows, verifications, api_calls, app_config,
-- api_keys, budget_ledger, outreach_tickets, audit_log, worker_heartbeats.
--
-- NOTE: bare `create table` statements (not `if not exists`) by design — this is
-- a fresh dev project applied once. Phase 0 polish backlog TODO: add `if not exists`
-- to support re-apply for demo workflows.

-- Required extensions
create extension if not exists pgcrypto;
create extension if not exists pg_trgm;
create extension if not exists "uuid-ossp";
-- pgmq is provisioned via Supabase Queues UI; do NOT create here.

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

-- verifications (APPEND-ONLY — triggers enforce in 0004)
-- NOTE: run_id has `on delete cascade` so test fixtures can clean up by deleting
-- the parent run. Application code does NOT issue raw deletes against runs in
-- normal flow; this cascade exists exclusively to enable test fixture teardown
-- (the BEFORE DELETE trigger on verifications fires on direct deletes but is
-- bypassed by cascade only via session_replication_role=replica).
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
-- Lives in 0001 because 0002 RLS policies reference it. 0007 is a placeholder.
create table public.worker_heartbeats (
  worker_id text primary key,
  last_seen_at timestamptz not null default now(),
  hostname text,
  version text
);
