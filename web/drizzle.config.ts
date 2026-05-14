import type { Config } from 'drizzle-kit'

// Drizzle is INTROSPECT-ONLY here (D-00-03).
// - `drizzle-kit pull`  → regenerates db/schema.ts from the live Supabase dev DB.
// - `drizzle-kit generate` is FORBIDDEN. Supabase CLI owns migrations.
// - CI (.github/workflows/codegen-drift.yml) re-runs `pull` and fails on any
//   diff against the committed schema.ts. A non-empty web/drizzle/migrations/
//   directory also fails CI (D-00-03 hard guard).
//
// Connection: DATABASE_URL (preferred) or SUPABASE_DEV_DB_URL fallback.
// Use the direct connection string (port 5432), not the pooler (6543).

export default {
  dialect: 'postgresql',
  schema: './db/schema.ts',
  out: './drizzle/.scratch', // scratch path; we never commit anything under here
  dbCredentials: {
    url: process.env.DATABASE_URL ?? process.env.SUPABASE_DEV_DB_URL ?? '',
  },
  introspect: { casing: 'preserve' },
  schemaFilter: ['public'],
} satisfies Config
