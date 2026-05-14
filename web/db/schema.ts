// Generated baseline derived from supabase/migrations/0001_init_schema.sql.
// In CI, `drizzle-kit pull` regenerates this file from the live Supabase dev DB
// and `git diff --exit-code` fails the build on any drift (Pitfall P4 defense).
//
// DO NOT hand-edit. To update:
//   1. Apply schema migration in supabase/migrations/
//   2. From web/: `pnpm exec drizzle-kit pull`
//   3. Commit the regenerated file.
//
// Live regeneration is deferred until the ivmf-checker-dev Supabase project is
// provisioned (see STATE.md Open Externally-Blocked Items).

import {
  pgTable,
  uuid,
  text,
  integer,
  bigserial,
  boolean,
  jsonb,
  numeric,
  timestamp,
  index,
  uniqueIndex,
  foreignKey,
} from 'drizzle-orm/pg-core'
import { sql } from 'drizzle-orm'

// ─── businesses ────────────────────────────────────────────────────────────────
export const businesses = pgTable(
  'businesses',
  {
    id: uuid('id').primaryKey().default(sql`gen_random_uuid()`),
    name: text('name').notNull(),
    normalized_name: text('normalized_name'),
    ein: text('ein'),
    website_domain: text('website_domain'),
    phone_e164: text('phone_e164'),
    address_normalized: jsonb('address_normalized'),
    city: text('city'),
    state: text('state'),
    match_signals: jsonb('match_signals').default(sql`'{}'::jsonb`),
    created_at: timestamp('created_at', { withTimezone: true })
      .notNull()
      .default(sql`now()`),
    updated_at: timestamp('updated_at', { withTimezone: true })
      .notNull()
      .default(sql`now()`),
  },
  (t) => ({
    ix_businesses_normalized_name: index('ix_businesses_normalized_name').on(
      t.normalized_name,
    ),
    ix_businesses_ein: index('ix_businesses_ein').on(t.ein),
  }),
)

// ─── runs ──────────────────────────────────────────────────────────────────────
export const runs = pgTable(
  'runs',
  {
    id: uuid('id').primaryKey().default(sql`gen_random_uuid()`),
    user_id: uuid('user_id').notNull(),
    status: text('status').notNull().default('pending'),
    source_filename: text('source_filename'),
    row_count: integer('row_count'),
    cost_estimate_cents: integer('cost_estimate_cents').default(0),
    cost_actual_cents: integer('cost_actual_cents').default(0),
    paused_at: timestamp('paused_at', { withTimezone: true }),
    pause_reason: text('pause_reason'),
    completed_at: timestamp('completed_at', { withTimezone: true }),
    created_at: timestamp('created_at', { withTimezone: true })
      .notNull()
      .default(sql`now()`),
    updated_at: timestamp('updated_at', { withTimezone: true })
      .notNull()
      .default(sql`now()`),
  },
  (t) => ({
    ix_runs_user_id: index('ix_runs_user_id').on(t.user_id),
  }),
)

// ─── run_rows ──────────────────────────────────────────────────────────────────
export const run_rows = pgTable(
  'run_rows',
  {
    id: uuid('id').primaryKey().default(sql`gen_random_uuid()`),
    run_id: uuid('run_id')
      .notNull()
      .references(() => runs.id, { onDelete: 'cascade' }),
    row_index: integer('row_index').notNull(),
    source_payload: jsonb('source_payload').notNull(),
    business_id: uuid('business_id').references(() => businesses.id),
    passes_completed: integer('passes_completed').notNull().default(0),
    passes_required: integer('passes_required').notNull().default(1),
    status: text('status').notNull().default('pending'),
    error_reason: text('error_reason'),
    created_at: timestamp('created_at', { withTimezone: true })
      .notNull()
      .default(sql`now()`),
  },
  (t) => ({
    uq_run_rows_run_idx: uniqueIndex('run_rows_run_id_row_index_key').on(
      t.run_id,
      t.row_index,
    ),
  }),
)

// ─── verifications (APPEND-ONLY — triggers in 0004) ───────────────────────────
export const verifications = pgTable(
  'verifications',
  {
    id: uuid('id').primaryKey().default(sql`gen_random_uuid()`),
    business_id: uuid('business_id').references(() => businesses.id),
    run_id: uuid('run_id').references(() => runs.id, { onDelete: 'cascade' }),
    row_index: integer('row_index'),
    pass: integer('pass').notNull().default(1),
    method: text('method').notNull(),
    status: text('status'),
    confidence: numeric('confidence', { precision: 4, scale: 3 }),
    provenance: jsonb('provenance').default(sql`'{}'::jsonb`),
    match_signals: jsonb('match_signals').default(sql`'{}'::jsonb`),
    evidence: text('evidence'),
    source_url: text('source_url'),
    cost_cents: integer('cost_cents').default(0),
    from_cache: boolean('from_cache').default(false),
    created_at: timestamp('created_at', { withTimezone: true })
      .notNull()
      .default(sql`now()`),
  },
  (t) => ({
    uq_verifications_run_row_pass: uniqueIndex(
      'uq_verifications_run_row_pass',
    ).on(t.run_id, t.row_index, t.pass),
  }),
)

// ─── api_calls ─────────────────────────────────────────────────────────────────
export const api_calls = pgTable(
  'api_calls',
  {
    id: uuid('id').primaryKey().default(sql`gen_random_uuid()`),
    provider: text('provider').notNull(),
    request_hash: text('request_hash').notNull(),
    response_payload: jsonb('response_payload'),
    cost_cents: integer('cost_cents'),
    created_at: timestamp('created_at', { withTimezone: true })
      .notNull()
      .default(sql`now()`),
  },
  (t) => ({
    uq_api_calls_provider_hash: uniqueIndex('uq_api_calls_provider_hash').on(
      t.provider,
      t.request_hash,
    ),
  }),
)

// ─── app_config ────────────────────────────────────────────────────────────────
export const app_config = pgTable('app_config', {
  key: text('key').primaryKey(),
  value: jsonb('value').notNull(),
  description: text('description'),
  updated_at: timestamp('updated_at', { withTimezone: true })
    .notNull()
    .default(sql`now()`),
})

// ─── api_keys ──────────────────────────────────────────────────────────────────
export const api_keys = pgTable('api_keys', {
  id: uuid('id').primaryKey().default(sql`gen_random_uuid()`),
  provider: text('provider').notNull(),
  label: text('label'),
  key_ciphertext: text('key_ciphertext'),
  is_primary: boolean('is_primary').default(false),
  is_disabled: boolean('is_disabled').default(false),
  monthly_cap_cents: integer('monthly_cap_cents'),
  low_balance_threshold_cents: integer('low_balance_threshold_cents'),
  created_at: timestamp('created_at', { withTimezone: true })
    .notNull()
    .default(sql`now()`),
  updated_at: timestamp('updated_at', { withTimezone: true })
    .notNull()
    .default(sql`now()`),
})

// ─── budget_ledger ─────────────────────────────────────────────────────────────
export const budget_ledger = pgTable('budget_ledger', {
  id: bigserial('id', { mode: 'bigint' }).primaryKey(),
  api_key_id: uuid('api_key_id').references(() => api_keys.id),
  event_type: text('event_type').notNull(),
  cents: integer('cents').notNull(),
  running_total_cents: integer('running_total_cents'),
  provider_truth_cents: integer('provider_truth_cents'),
  meta: jsonb('meta').default(sql`'{}'::jsonb`),
  created_at: timestamp('created_at', { withTimezone: true })
    .notNull()
    .default(sql`now()`),
})

// ─── outreach_tickets ─────────────────────────────────────────────────────────
export const outreach_tickets = pgTable('outreach_tickets', {
  id: uuid('id').primaryKey().default(sql`gen_random_uuid()`),
  run_id: uuid('run_id').references(() => runs.id),
  status: text('status').notNull().default('pending'),
  token_hash: text('token_hash'),
  approved_by: uuid('approved_by'),
  created_at: timestamp('created_at', { withTimezone: true })
    .notNull()
    .default(sql`now()`),
})

// ─── audit_log ─────────────────────────────────────────────────────────────────
export const audit_log = pgTable('audit_log', {
  id: bigserial('id', { mode: 'bigint' }).primaryKey(),
  actor_user_id: uuid('actor_user_id'),
  action: text('action').notNull(),
  table_name: text('table_name').notNull(),
  row_pk: text('row_pk'),
  before: jsonb('before'),
  after: jsonb('after'),
  diff: jsonb('diff'),
  request_id: text('request_id'),
  created_at: timestamp('created_at', { withTimezone: true })
    .notNull()
    .default(sql`now()`),
})

// ─── worker_heartbeats ─────────────────────────────────────────────────────────
export const worker_heartbeats = pgTable('worker_heartbeats', {
  worker_id: text('worker_id').primaryKey(),
  last_seen_at: timestamp('last_seen_at', { withTimezone: true })
    .notNull()
    .default(sql`now()`),
  hostname: text('hostname'),
  version: text('version'),
})
