# Phase 0: Foundation — Research

**Researched:** 2026-05-12
**Domain:** Multi-app monorepo bootstrap — Supabase Postgres (schema/RLS/pgmq/triggers/cron) + Next.js 16 App Router (auth + middleware) + Railway Python worker (FastAPI + pgmq consumer) + codegen drift gate + eval-CI gate
**Confidence:** HIGH (versions and patterns cross-verified in `.planning/research/STACK.md` 2026-05-12 against npm + PyPI registries; Phase 0 specifics derived from CONTEXT.md locked decisions D-00-01..D-00-11)

## Summary

Phase 0 is a pure infrastructure phase. No business logic ships. Six pillars must be green by exit: (1) Supabase project with the full v1.1 schema and RLS, (2) append-only triggers + idempotency UNIQUE keys on `verifications`, (3) magic-link auth gated by `@syr.edu` allowlist at BOTH Next.js middleware AND a Postgres RLS function, (4) Railway worker scaffold long-polling `q_verify`/`q_aggregator` with vt=300s and emitting a heartbeat row, (5) two-language codegen pipeline (Drizzle introspect for TS + datamodel-code-generator for Python) wired into a CI drift gate, (6) v1.0 eval harness running on every PR with a baseline-regression block.

The entire phase is constrained by `.planning/research/` — STACK.md (versions locked), ARCHITECTURE.md (topology + module layout), PITFALLS.md (P1, P4, P7, P10, P11, P12 land in Phase 0). The planner should treat those three files plus CONTEXT.md as the source of truth and use this document as the synthesis index pointing at the specific patterns and verification steps for each Phase 0 deliverable.

**Primary recommendation:** Sequence the work as five waves — (A) Supabase schema + RLS + triggers + pgmq, (B) codegen pipeline + CI drift gate, (C) Next.js shell + magic-link + middleware + `/me`, (D) Railway worker scaffold + heartbeat + pgmq long-poll, (E) eval-CI gate + Resend DNS ticket. Wave A blocks B–D. Land the drift-trip PR (D-00-11 item 2) before Wave E so subsequent phases can't regress on it.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-00-01 Repo layout:** Monorepo with `web/` (Next.js → Vercel), `worker/` (FastAPI + imports `business_checker/` via `pip install -e ../business_checker` → Railway), `supabase/` (migrations, RLS, triggers, cron, seed). Tkinter GUI files (`business_checker_gui.py`, `business_checker_app.py`, `run_checker.py`) stay frozen at v1.0 — DO NOT delete or refactor.
- **D-00-02 Dev environment:** Cloud-only dev against a dedicated `ivmf-checker-dev` Supabase project. No `supabase start` / Docker. Production is a separate project. `.env.local` (web) and `.env` (worker) point to dev; production keys live in Vercel + Railway env settings.
- **D-00-03 Migration tooling:** Supabase CLI is the SINGLE source of truth for schema, RLS, triggers, functions, cron. `supabase/migrations/*.sql` files are hand-written or exported from dashboard. **Drizzle is introspect-only** (`drizzle-kit pull`). **`drizzle-kit generate` is forbidden.** CI guard must fail if anything under `drizzle/migrations/` exists.
- **D-00-04 Auth UX:** Magic-link ONLY in Phase 0. No password sign-up, no password reset, no password field on sign-in page. AUTH-01 satisfied via the "or" clause. Sign-in page = one input (email) + one button (send magic link). Server validates `@syr.edu` against `app_config.email_domain_allowlist` BEFORE calling `supabase.auth.signInWithOtp()`.
- **D-00-05 Domain allowlist:** `app_config` table row `(key='email_domain_allowlist', value='["syr.edu"]'::jsonb)`. Next.js middleware reads this with 60s edge cache. Postgres RLS function `auth.is_allowed_domain(email text) returns boolean` reads the same row and is referenced by the policy on `auth.users`. BOTH layers MUST enforce. Admin extends allowlist by editing the config row — no code change (AUTH-02).
- **D-00-06 Audit log:** Single `audit_log` table `(id, actor_user_id, action, table_name, row_pk, before jsonb, after jsonb, diff jsonb, created_at, request_id)`. Generic `audit_log_trigger()` function uses `TG_TABLE_NAME`, `TG_OP`, `OLD`, `NEW`. Attached to `app_config`, `api_keys`, `budget_ledger`, and a stub on `outreach_tickets`. `diff` column computed in trigger via `jsonb_object_agg` of changed keys.
- **D-00-07 Append-only triggers:** `BEFORE UPDATE` and `BEFORE DELETE` triggers on `verifications` raise `EXCEPTION 'verifications is append-only — use INSERT with method=admin_edit'`. Unconditional (no service-role bypass). Integration test asserts SQLSTATE.
- **D-00-08 Idempotency UNIQUE keys:** `verifications UNIQUE (run_id, row_index, pass)`. `api_calls UNIQUE (provider, request_hash)`. Both columns NOT NULL on insert. `api_calls` table created in Phase 0 even though no calls happen until Phase 2.
- **D-00-09 pgmq config:** `pgmq.create('q_verify')` + `pgmq.create('q_aggregator')`. **vt=300s configured at the consumer call site, NOT at create time** (pgmq vt is per-read in tembo-pgmq-python 0.10). Worker uses `read_with_poll(queue, vt=300, qty=1, max_poll_seconds=20)`.
- **D-00-10 Upload-parse allowlist:** `app_config` row stores allowed source-column header set (initially BMSG/MWBE public-registry headers). Phase 0 stubs the upload endpoint with a parse function that rejects out-of-allowlist headers. Upload UI ships in Phase 1; parse function unit-tested in Phase 0 against the two reference Run input files.
- **D-00-11 Phase 0 demo (exit criteria — all 6 must pass in one 10-min walkthrough):**
  1. `@syr.edu` magic-link login → `/me` page with email + role; `@gmail.com` blocked at middleware with clear message.
  2. PR dropping/renaming a column in `supabase/migrations/*.sql` without regenerating Drizzle + Pydantic fails CI on non-zero diff from `drizzle-kit pull` or `datamodel-codegen`.
  3. PR introducing eval gold-set regression (flipped label) fails eval-CI step.
  4. `UPDATE verifications` raises append-only exception; duplicate `INSERT` with same `(run_id, row_index, pass)` raises unique-violation.
  5. Worker on Railway has long-polled `q_verify` for ≥1 cycle and shows a row in `worker_heartbeats`.
  6. Resend DNS ticket for IVMF subdomain filed with IT, ticket ID logged in STATE.md.

### Claude's Discretion

- Exact Postgres column types (use Drizzle / datamodel-code-generator defaults; document deviations).
- Folder layout inside `web/`, `worker/`, `supabase/` (follow Next.js App Router conventions; FastAPI module layout per `.planning/research/ARCHITECTURE.md` §Worker module inventory).
- CI provider — pick **GitHub Actions** unless stronger reason emerges.
- Heartbeat watchdog implementation: pg_cron OR worker self-loop in Phase 0 (research suggests pg_cron; either acceptable as long as the demo can read the row).
- Test frameworks: **pytest** for worker, **vitest** for web.
- Specific shape of `/me` page beyond "shows email and role" — minimal styling acceptable.

### Deferred Ideas (OUT OF SCOPE)

- Password authentication UX (deferred to v1.2 if IVMF staff push back).
- CI on Railway/Vercel instead of GitHub Actions.
- Supabase local Docker dev environment.
- Multi-environment promotion (dev → staging → prod).
- Audit log retention/archival policy.
- Outreach token HMAC implementation (Phase 4).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AUTH-01 | User can sign in with `@syr.edu` email via magic-link or password | Magic-link only this phase (D-00-04). Supabase Auth `signInWithOtp()` with email allowlist check pre-call (server action). |
| AUTH-02 | Admin can extend email domain allowlist via config row (no code change) | `app_config` table with `email_domain_allowlist` jsonb row read by both middleware and `auth.is_allowed_domain()` RLS function (D-00-05). |
| AUTH-03 | Two-role RBAC (admin / user) via Next.js middleware AND Postgres RLS, role stored in `app_metadata` | Role written to `auth.users.raw_app_meta_data->>'role'` via Supabase admin client; middleware reads from JWT claims; RLS policies use `auth.jwt() ->> 'role'`. |
| AUTH-04 | Audit log entry with before/after diff for every admin write | `audit_log_trigger()` generic function + ON UPDATE triggers on `app_config`, `api_keys`, `budget_ledger`, `outreach_tickets` stub (D-00-06). |
| CANON-03 | Normalize name / domain / phone / address before matching | usaddress 0.5.16 + custom normalizers. Phase 0 lands the helper module + unit tests; full matching logic is Phase 1. |
| CANON-05 | Create a new canonical business row when no match meets threshold | Phase 0 lands the `businesses` table schema + uniqueness shape; full match-and-create flow is Phase 1. |
| CANON-06 | Append-only `verifications` with BEFORE UPDATE/DELETE triggers raising | D-00-07 unconditional trigger. Integration test asserts SQLSTATE 'P0001'. |
| CANON-07 | Idempotency UNIQUE on `(run_id, row_index, pass)` + `(provider, request_hash)` | D-00-08. Both tables ship in Phase 0 even though `api_calls` is unused until Phase 2. |
| CANON-08 | Per-row provenance on every verification (matched fields, score, method) | `verifications.provenance jsonb` + `method text NOT NULL` + `match_signals jsonb`. Column shape lands in Phase 0; Phase 1+ writes data. |
| ANALYTICS-04 | Eval harness runs on every worker deploy in CI; deploy blocked on regression below baseline | GitHub Actions job runs `python -m business_checker.eval.score`; compares `accuracy.json` to committed baseline; exits non-zero if below. Includes `assert n_examples >= MIN` (Pitfall 8). |
</phase_requirements>

## Standard Stack

> All versions verified in `.planning/research/STACK.md` against npm + PyPI registries on 2026-05-12. The planner should pin these in `web/package.json` and `worker/pyproject.toml`. Confirm against `npm view <pkg> version` and `pip index versions <pkg>` at the moment of implementation if more than ~14 days have passed since 2026-05-12.

### Core (NEW for Phase 0)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `next` | 16.2.6 | App Router shell, middleware, server actions, route handlers | Locked in PROJECT.md; Vercel-native; App Router is the only supported path going forward |
| `react` | 19.2.6 | Pinned by Next 16; Server Components default | Bundled |
| `@supabase/supabase-js` | 2.105.4 | Server + browser SDK | Standard pair with Supabase Postgres |
| `@supabase/ssr` | 0.10.3 | Cookie-bound auth in Next.js App Router (`createServerClient`/`createBrowserClient`) | Replaces deprecated `@supabase/auth-helpers-nextjs`. **Use `getUser()` in middleware/server components — never `getSession()` from cookies alone** (Supabase canonical guidance — STACK.md anti-patterns). |
| `drizzle-orm` | 0.45.2 | TS schema reflection + types from Postgres | `drizzle-kit pull` only — generate is forbidden (D-00-03) |
| `drizzle-kit` | ^0.45 | Introspect-only CLI | Generates `db/schema.ts` from live DB |
| `zod` | 4.4.3 | Boundary validation (sign-in form, upload-parse, config edits) | Standard validation layer |
| `tailwindcss` | 4.3.0 | Styling for `/me` and sign-in pages | Ships native with Next 16, no PostCSS config |
| `fastapi` | 0.136.1 | Worker HTTP surface: `/health`, `/heartbeat`, internal endpoints | Standard FastAPI stack |
| `uvicorn[standard]` | 0.35.x | ASGI server | Standard pairing |
| `psycopg[binary,pool]` | 3.3.4 | Postgres driver with pool; sync + async; service-role direct connection (NOT via PostgREST/supabase-py) | psycopg3, not psycopg2 |
| `tembo-pgmq-python` | 0.10.0 | pgmq client (read_with_poll, set_vt, archive, delete) | Official pgmq client; vt is per-read (D-00-09) |
| `tenacity` | 9.1.4 | Retry/backoff (Phase 0 imports it as a dep; usage is Phase 2) | Standard |
| `structlog` | 25.x latest | Structured logs with `run_id` correlation | Required for audit/observability |
| `pydantic` | 2.12.5 | Models (already in `business_checker`); kept for worker | v2 mandatory; `extra='forbid'` for codegen models (Pitfall 4) |
| `datamodel-code-generator` | 0.57.0 | Python codegen from Postgres → pydantic v2 models | Dev-time dep; runs in CI |

### Supporting (Phase 0 only — minimum to satisfy demo)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `supabase` (CLI) | latest | Migrations (`supabase migration new`, `supabase db push`) | Single source of truth for schema/RLS/triggers/cron |
| `postgres` (npm) | latest | Connection client for Drizzle | Pairs with `drizzle-orm` for runtime queries |
| `@supabase/supabase-js` types via `supabase gen types typescript` | bundled CLI | `Database` generic for `createClient<Database>` | Used alongside Drizzle (STACK.md) |

**Deliberately deferred to later phases** (do NOT install in Phase 0): `papaparse`, `@tanstack/react-table`, `react-hook-form`, `react-email`, `usaddress`, `httpx`, `supabase` Python SDK, `resend`. They add surface area Phase 0 doesn't need.

### Alternatives Considered (already settled in STACK.md — do not re-litigate)

| Standard | Rejected | Why |
|----------|----------|-----|
| Magic-link | Password sign-in this phase | D-00-04 — smallest Phase 0 surface |
| GitHub Actions | Vercel/Railway CI | Free at this scale; first-party GitHub integration on both deploy targets |
| Supabase CLI migrations | Drizzle migrations | Drizzle's RLS/trigger DSL is incomplete in 0.45 (STACK.md ORM rationale) |
| psycopg3 | psycopg2 / asyncpg / supabase-py for queries | EOL track / async-only / extra network hop |
| Cloud dev Supabase project | `supabase start` Docker | D-00-02 — laptop-first workflow |
| Railway | Vercel/Lambda for worker | 15-min and 400s wall-clock caps incompatible with hours-long Phase 2 runs (STACK.md anti-patterns) |

### Installation

```bash
# web/
pnpm create next-app@16 web --typescript --tailwind --app --no-src-dir
cd web
pnpm add @supabase/supabase-js@2.105.4 @supabase/ssr@0.10.3 zod@4.4.3 \
         drizzle-orm@0.45.2 postgres
pnpm add -D drizzle-kit@^0.45 supabase

# worker/
python -m venv .venv && source .venv/bin/activate
pip install fastapi==0.136.1 'uvicorn[standard]' \
            'psycopg[binary,pool]==3.3.4' \
            tembo-pgmq-python==0.10.0 \
            tenacity==9.1.4 \
            structlog \
            pydantic==2.12.5
pip install -e ../business_checker   # editable install per D-00-01

# dev-time
pip install datamodel-code-generator==0.57.0
```

**Version verification (run at implementation time):**
```bash
npm view next@16 version            # expect 16.2.x
npm view @supabase/ssr version      # expect 0.10.x
pip index versions psycopg          # expect 3.3.x
pip index versions tembo-pgmq-python # expect 0.10.x
```

## Architecture Patterns

### Recommended Project Structure

```
ivmf-business-checker/
├── business_checker/           # PRESERVED v1.0 engine — installable package
│   ├── pyproject.toml          # already present; declares the package
│   ├── tools/                  # check_business, scrape_website, columns, build_output, aggregator
│   ├── eval/                   # gold set + score.py
│   └── tests/
├── web/                        # NEW — Next.js 16 (Vercel)
│   ├── package.json
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── drizzle.config.ts       # introspect-only config
│   ├── middleware.ts           # domain allowlist + role check at edge
│   ├── app/
│   │   ├── (auth)/sign-in/page.tsx
│   │   ├── me/page.tsx
│   │   ├── api/auth/callback/route.ts   # magic-link callback
│   │   └── layout.tsx
│   ├── db/
│   │   ├── schema.ts           # generated by drizzle-kit pull (committed)
│   │   └── types.ts            # supabase gen types typescript output
│   ├── lib/supabase/
│   │   ├── server.ts           # createServerClient (cookies-bound)
│   │   ├── client.ts           # createBrowserClient
│   │   └── service-role.ts     # service role (server-only env)
│   ├── lib/auth/
│   │   └── allowlist.ts        # reads app_config.email_domain_allowlist
│   └── tests/                  # vitest
├── worker/                     # NEW — FastAPI (Railway)
│   ├── pyproject.toml
│   ├── Procfile or railway.json
│   ├── workers/
│   │   ├── main.py             # FastAPI app: /health, /heartbeat
│   │   ├── dispatcher.py       # pgmq long-poll loop (stub in Phase 0)
│   │   ├── heartbeat.py        # writes worker_heartbeats row every ~30s
│   │   └── lib/
│   │       ├── db.py           # psycopg pool
│   │       ├── pgmq_client.py  # tembo-pgmq-python wrapper, vt=300 at call site
│   │       └── models.py       # GENERATED — pydantic from datamodel-code-generator
│   └── tests/                  # pytest
├── supabase/                   # NEW — schema source of truth
│   ├── config.toml
│   ├── migrations/
│   │   ├── 0001_init_schema.sql        # tables, FKs, indexes
│   │   ├── 0002_rls_policies.sql       # RLS enable + policies
│   │   ├── 0003_audit_log_trigger.sql  # generic trigger function + attachments
│   │   ├── 0004_verifications_append_only.sql   # BEFORE UPDATE/DELETE raise
│   │   ├── 0005_pgmq_queues.sql        # pgmq.create('q_verify') + ('q_aggregator')
│   │   ├── 0006_app_config_seed.sql    # email_domain_allowlist + column allowlist
│   │   └── 0007_worker_heartbeats.sql
│   └── seed.sql                # local seeding for dev
├── .github/workflows/
│   ├── codegen-drift.yml       # drizzle pull + datamodel-codegen → git diff --exit-code
│   ├── eval-ci.yml             # python -m business_checker.eval.score
│   └── ci.yml                  # lint, test, type-check (vitest + pytest)
└── .planning/                  # GSD planning artifacts (already present)
```

### Pattern 1: Domain Allowlist — Defense in Depth (Middleware + RLS)

**What:** Enforce `@syr.edu` (or whatever `app_config` says) at BOTH the Next.js edge middleware AND the Postgres RLS layer. Reading only one is a known-bypass shape (CONTEXT.md D-00-05).

**When to use:** Every request to a protected route AND every auth-server interaction.

**Pattern (Next.js 16 App Router middleware — verified against `@supabase/ssr` 0.10.x official guidance):**

```ts
// web/middleware.ts
import { NextRequest, NextResponse } from 'next/server'
import { createServerClient } from '@supabase/ssr'

// Edge-cached allowlist read; 60s TTL.
let allowlistCache: { value: string[]; expiresAt: number } | null = null

async function getAllowlist(supabase: ReturnType<typeof createServerClient>): Promise<string[]> {
  const now = Date.now()
  if (allowlistCache && allowlistCache.expiresAt > now) return allowlistCache.value
  const { data } = await supabase
    .from('app_config')
    .select('value')
    .eq('key', 'email_domain_allowlist')
    .single()
  const value = (data?.value as string[]) ?? ['syr.edu']
  allowlistCache = { value, expiresAt: now + 60_000 }
  return value
}

export async function middleware(req: NextRequest) {
  const res = NextResponse.next()
  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll: () => req.cookies.getAll(),
        setAll: (toSet) => toSet.forEach(({ name, value, options }) =>
          res.cookies.set(name, value, options))
      }
    }
  )

  // CRITICAL: getUser() hits the auth server and validates the token.
  // Do NOT use getSession() here — cookie alone is not authenticated.
  const { data: { user } } = await supabase.auth.getUser()

  const protectedPath = !req.nextUrl.pathname.startsWith('/sign-in')
                     && !req.nextUrl.pathname.startsWith('/api/auth')

  if (protectedPath && !user) {
    return NextResponse.redirect(new URL('/sign-in', req.url))
  }

  if (user) {
    const allowlist = await getAllowlist(supabase)
    const domain = user.email?.split('@')[1] ?? ''
    if (!allowlist.includes(domain)) {
      // 403 with clear message — required by D-00-11 item 1
      return new NextResponse(
        `Sign-in restricted to allowed domains: ${allowlist.join(', ')}`,
        { status: 403 }
      )
    }
  }
  return res
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)']
}
```

**Pattern (Postgres RLS function — defense layer 2):**

```sql
-- supabase/migrations/0006_app_config_seed.sql (excerpt)
create or replace function auth.is_allowed_domain(email text)
returns boolean
language sql
stable
security definer
set search_path = public, auth
as $$
  select exists (
    select 1
    from app_config
    where key = 'email_domain_allowlist'
      and value ?| array[ split_part(email, '@', 2) ]
  );
$$;

-- Triggered on auth.users insert (Supabase exposes this via a trigger; alternatively,
-- gate at the server action before signInWithOtp() AND assert via this function from
-- any service-role write that touches auth-derived state).
create or replace function public.enforce_domain_on_signup()
returns trigger
language plpgsql
security definer
as $$
begin
  if not auth.is_allowed_domain(NEW.email) then
    raise exception 'Email domain not in allowlist: %', NEW.email
      using errcode = 'P0001';
  end if;
  return NEW;
end;
$$;

create trigger trg_enforce_domain
  before insert on auth.users
  for each row execute function public.enforce_domain_on_signup();
```

**Verification:** Sign in with `@gmail.com` — middleware returns 403; if middleware is somehow bypassed, the database trigger blocks the row insert.

### Pattern 2: Append-Only Triggers on `verifications`

**What:** Unconditional `BEFORE UPDATE`/`BEFORE DELETE` triggers raise. Not even service-role can bypass (D-00-07).

```sql
-- supabase/migrations/0004_verifications_append_only.sql
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

-- Idempotency (D-00-08)
alter table public.verifications
  add constraint uq_verifications_run_row_pass
  unique (run_id, row_index, pass);

-- api_calls table — Phase 0 schema only, no calls until Phase 2
create table if not exists public.api_calls (
  id uuid primary key default gen_random_uuid(),
  provider text not null,
  request_hash text not null,
  response_payload jsonb,
  cost_cents integer,
  created_at timestamptz default now(),
  constraint uq_api_calls_provider_hash unique (provider, request_hash)
);
```

**Integration test:** assert `psycopg.errors.RaiseException` (PG SQLSTATE `P0001`) on a direct UPDATE; assert `psycopg.errors.UniqueViolation` (`23505`) on the second INSERT.

### Pattern 3: Generic Audit Log Trigger

```sql
-- supabase/migrations/0003_audit_log_trigger.sql
create table if not exists public.audit_log (
  id bigserial primary key,
  actor_user_id uuid references auth.users(id),
  action text not null,            -- INSERT / UPDATE / DELETE
  table_name text not null,
  row_pk text,                     -- stringified primary key
  before jsonb,
  after jsonb,
  diff jsonb,
  request_id text,                 -- correlation id from app
  created_at timestamptz default now()
);

create or replace function public.audit_log_trigger()
returns trigger
language plpgsql
security definer
as $$
declare
  v_before jsonb;
  v_after jsonb;
  v_diff jsonb;
  v_pk text;
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

-- Attach to admin-writable tables
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
```

**Setting `request_id`:** Web/worker should `SET LOCAL app.request_id = $1` at transaction start. If unset, the audit row still writes with `request_id IS NULL` — acceptable degradation.

### Pattern 4: pgmq Queues + Worker Long-Poll

**Create queues (migration):**
```sql
-- supabase/migrations/0005_pgmq_queues.sql
-- pgmq extension is bundled with Supabase Queues GA
select pgmq.create('q_verify');
select pgmq.create('q_aggregator');
```

**Worker consumption (vt=300 at the call site — D-00-09):**
```python
# worker/workers/lib/pgmq_client.py
from tembo_pgmq_python import PGMQueue
from typing import Optional

class QueueClient:
    def __init__(self, dsn: str):
        self.q = PGMQueue(host=..., port=..., username=..., password=..., database=...)
        # Or PGMQueue.from_dsn(dsn) per 0.10.0 API — verify with `help(PGMQueue)`

    def read_one(self, queue: str, vt_seconds: int = 300, poll_seconds: int = 20):
        # vt is per-read, NOT a queue-level setting (D-00-09; STACK.md)
        msgs = self.q.read_with_poll(
            queue=queue,
            vt=vt_seconds,
            qty=1,
            max_poll_seconds=poll_seconds,
        )
        return msgs[0] if msgs else None

    def archive(self, queue: str, msg_id: int) -> None:
        self.q.archive(queue, msg_id)

    def extend_vt(self, queue: str, msg_id: int, additional_seconds: int) -> None:
        # heartbeat extension during long-running jobs (Phase 2 usage)
        self.q.set_vt(queue, msg_id, additional_seconds)
```

**Phase 0 dispatcher (stub — does not process payloads):**
```python
# worker/workers/dispatcher.py
async def loop():
    while not shutdown.is_set():
        msg = qclient.read_one('q_verify', vt_seconds=300, poll_seconds=20)
        if msg is None:
            continue
        log.info('q_verify.message', msg_id=msg.msg_id)
        # Phase 0: just archive — no business logic
        qclient.archive('q_verify', msg.msg_id)
```

### Pattern 5: Worker Heartbeat Row

```sql
-- supabase/migrations/0007_worker_heartbeats.sql
create table if not exists public.worker_heartbeats (
  worker_id text primary key,
  last_seen_at timestamptz not null default now(),
  hostname text,
  version text
);
```

```python
# worker/workers/heartbeat.py — runs every 30s in a background asyncio task
async def heartbeat_loop():
    while not shutdown.is_set():
        await db.execute("""
            insert into worker_heartbeats (worker_id, last_seen_at, hostname, version)
            values (%s, now(), %s, %s)
            on conflict (worker_id) do update
              set last_seen_at = now(),
                  hostname = excluded.hostname,
                  version  = excluded.version
        """, (WORKER_ID, socket.gethostname(), os.getenv('GIT_SHA', 'dev')))
        await asyncio.sleep(30)
```

Demo verification (D-00-11 item 5): `SELECT * FROM worker_heartbeats` on Supabase shows a row within 30s of Railway deploy.

### Pattern 6: Codegen Drift Gate

**CI workflow:**
```yaml
# .github/workflows/codegen-drift.yml
name: codegen-drift
on: [pull_request]
jobs:
  drift:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v3
      - uses: actions/setup-node@v4
        with: { node-version: '22' }
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - name: Install deps
        run: |
          pnpm --filter ./web install
          pip install datamodel-code-generator==0.57.0
      # Hard guard against forbidden Drizzle migrations (D-00-03)
      - name: No Drizzle migrations
        run: |
          if [ -d web/drizzle/migrations ] && [ "$(ls -A web/drizzle/migrations 2>/dev/null)" ]; then
            echo "ERROR: web/drizzle/migrations must be empty — Supabase CLI owns migrations (D-00-03)"; exit 1
          fi
      - name: Drizzle introspect
        env: { DATABASE_URL: ${{ secrets.SUPABASE_DEV_DB_URL }} }
        run: pnpm --filter ./web exec drizzle-kit pull
      - name: Pydantic codegen
        env: { DATABASE_URL: ${{ secrets.SUPABASE_DEV_DB_URL }} }
        run: |
          datamodel-codegen \
            --input-file-type postgres \
            --url "$DATABASE_URL" \
            --output worker/workers/lib/models.py \
            --output-model-type pydantic_v2.BaseModel \
            --use-schema-description
      - name: Assert no diff
        run: git diff --exit-code -- web/db/schema.ts worker/workers/lib/models.py
```

**Trip the demo (D-00-11 item 2):** A PR that drops a column from `supabase/migrations/*.sql` will cause `drizzle-kit pull` to regenerate `web/db/schema.ts` without that column. `git diff --exit-code` then sees the diff and exits non-zero. Same for `models.py`.

### Pattern 7: Eval-CI Regression Gate

```yaml
# .github/workflows/eval-ci.yml
name: eval-ci
on: [pull_request, push]
jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - name: Install business_checker
        run: pip install -e ./business_checker
      - name: Run eval
        env:
          PERPLEXITY_API_KEY: ${{ secrets.PERPLEXITY_API_KEY_EVAL }}
        run: |
          python -m business_checker.eval.score --gold business_checker/eval/gold.json --out eval_result.json
      - name: Assert gold set size (Pitfall 8 defense)
        run: |
          python -c "import json; r=json.load(open('eval_result.json')); assert r['n_examples'] >= 20, f'gold set too small: {r[\"n_examples\"]}'"
      - name: Compare to baseline
        run: |
          python -c "
          import json
          r = json.load(open('eval_result.json'))
          b = json.load(open('business_checker/eval/baseline.json'))
          assert r['accuracy'] >= b['accuracy'] - 0.01, \
            f'eval regression: {r[\"accuracy\"]:.3f} < baseline {b[\"accuracy\"]:.3f} - 0.01'
          "
```

**Trip the demo (D-00-11 item 3):** A PR that flips an expected label in `business_checker/eval/gold.json` lowers measured accuracy → assertion fails → CI red.

**Note:** If `business_checker/eval/score.py` doesn't currently emit `n_examples` or `accuracy` in JSON, that adjustment is part of the v1.0 polish precondition (STATE.md §Phase 0 Preconditions). Verify the file exists; if it emits a different shape, the planner should land a minimal shim in the eval workflow (do NOT modify the engine code in Phase 0 — preservation rule).

### Anti-Patterns to Avoid (Phase 0 specific)

- **`getSession()` in middleware/server components** — tokens come from cookies and aren't validated. Use `getUser()` (Supabase canonical guidance; STACK.md anti-patterns).
- **Service-role key with `NEXT_PUBLIC_` prefix** — total RLS bypass from the browser. Service role lives in Vercel server env + Railway env only.
- **`@supabase/auth-helpers-nextjs`** — deprecated by Supabase. Use `@supabase/ssr` 0.10.3.
- **Drizzle migrations** — D-00-03 forbids them. CI must hard-fail on `web/drizzle/migrations/*.sql`.
- **pgmq vt at queue creation** — vt is per-read in tembo-pgmq-python 0.10. Setting it at create time is silently ignored.
- **Allowlist enforcement at middleware OR RLS, not both** — known-bypass shape per CONTEXT.md D-00-05.
- **`extra='ignore'` on generated Pydantic models** — silent column drift (Pitfall 4). Use `extra='forbid'`.
- **Eval CI using the anon key** — RLS filters rows, gold set looks tiny, eval false-passes (Pitfall 8). Use service-role; assert minimum size.
- **Reading `verifications` for live progress in the browser** — RLS doesn't auto-apply to Realtime publications (Pitfall 12). Phase 0 doesn't ship a progress UI but the planner should not seed shortcuts that violate this.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Magic-link auth flow | Custom email + token table | Supabase Auth `signInWithOtp()` + `/api/auth/callback` route | Battle-tested email delivery, OTP shape, replay protection, JWT issuance |
| Cookie-bound session handling in App Router | Manual cookie + JWT parsing | `@supabase/ssr` 0.10.3 (`createServerClient` / `createBrowserClient`) | Replaces deprecated `auth-helpers-nextjs`; correct PKCE + cookie patterns |
| Postgres durable queue | Custom polling table | `pgmq` (Supabase Queues GA) + `tembo-pgmq-python` 0.10.0 | Transactional enqueue with row writes, visibility timeouts, archive — solved problem |
| Audit log row generation | Hand-write per table | Generic `audit_log_trigger()` with `TG_TABLE_NAME` / `TG_OP` (D-00-06) | One function reused; new tables get audit by adding a trigger line |
| TS schema types | Hand-maintain TS interfaces | `drizzle-kit pull` → `db/schema.ts` + `supabase gen types typescript` | Both regenerate from Postgres; drift gate catches divergence |
| Python schema models | Hand-write Pydantic models | `datamodel-code-generator` 0.57.0 from Postgres URL | Same drift gate; `extra='forbid'` makes drift loud (Pitfall 4) |
| Per-row idempotency | Hand-checked dedup at insert time | `UNIQUE (run_id, row_index, pass)` + `INSERT … ON CONFLICT DO NOTHING` (Phase 2) | DB-enforced; can't be bypassed by misplaced retry logic (Pitfall 1) |
| Append-only enforcement | Application-layer "don't UPDATE" convention | `BEFORE UPDATE/DELETE` raise trigger (D-00-07) | Unbypassable; service role cannot defeat it |
| Heartbeat tracking | External monitor pinging worker | `worker_heartbeats` UPSERT every 30s | Single source of truth in DB; same query for Phase 2 watchdog |
| Eval CI scorer | Custom test runner | Existing `business_checker.eval.score` module | Already exists; Phase 0 wires it into GitHub Actions only |

**Key insight:** Phase 0 success comes from accepting that Supabase + Drizzle + datamodel-code-generator + pgmq + the existing eval harness solve every Phase 0 problem. Custom code introduced here multiplies risk across every later phase.

## Runtime State Inventory

> This is a greenfield infrastructure phase, not a rename/refactor. The relevant inventory is "what's about to exist" rather than "what's already running with old names."

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | **None** — Phase 0 ships empty schemas. The dev Supabase project should be created empty; production project remains empty until Phase 1. The v1.0 SQLite cache at `business_checker/cache/` is being deprecated but is NOT migrated in Phase 0 (Phase 1 lookup will hit `business_current_state`, not the old cache). | None — verify `business_checker/cache/` remains untouched; v1.0 desktop continues to read it if needed. |
| Live service config | **None for Phase 0** — but a Resend account + IVMF subdomain DNS ticket must be FILED (not completed) per D-00-11 item 6. Track the ticket ID in STATE.md. | File IT ticket; capture ticket ID. |
| OS-registered state | **None** — no cron / systemd / Task Scheduler involved. pg_cron (if used for heartbeat watchdog) lives inside Supabase and is configured by SQL migration. | None — verified by absence of background daemons in the design. |
| Secrets / env vars | New env vars to create (NOT pre-existing): `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` (web + worker), `DATABASE_URL` (worker direct psycopg + drizzle introspect), `PERPLEXITY_API_KEY_EVAL` (CI eval gate only — separate from prod Perplexity key per STATE.md key-rotation note). | Create env-var rows in Vercel (web) and Railway (worker); add to GitHub Actions secrets. Commit `.env.example` files only. |
| Build artifacts / installed packages | `business_checker/business_checker.egg-info/` will be created by `pip install -e ../business_checker` in the worker venv. This is generated; should be in `.gitignore`. The package name in `business_checker/pyproject.toml` must be `business_checker` (verify before Phase 0 start; this is part of the precondition polish pass). | Confirm `pyproject.toml` declares `[project] name = "business_checker"`; add `*.egg-info/` to `.gitignore` if not already present. |

**Canonical question — "After Phase 0 ships, what runtime systems exist that didn't before?"** Answer: a dev Supabase project, a Vercel preview deployment of `web/`, a Railway service for `worker/`, three GitHub Actions workflows (codegen-drift, eval-ci, ci), and an IT ticket for Resend DNS. Each of these has a config surface the planner must track in plan tasks.

## Common Pitfalls

> Full pitfall catalog is `.planning/research/PITFALLS.md`. Phase 0 specifically must prevent P1, P4, P7, P10, P11, P12. P2, P5, P6, P8, P9 are downstream-phase concerns the Phase 0 schema enables.

### P1: Double-Billing on API Retries (schema groundwork in Phase 0)

**What goes wrong:** Retry logic placed around the whole verify-and-insert block, not just the API call → duplicate Perplexity bills.

**Why it happens:** No idempotency lock at the API-call layer; idempotency only on the DB row.

**How Phase 0 addresses it:** Ship the `api_calls UNIQUE (provider, request_hash)` schema (D-00-08) and the `verifications UNIQUE (run_id, row_index, pass)`. Phase 2 will add the `ON CONFLICT DO NOTHING` insert-before-call pattern, but it cannot be added without the schema.

**Warning signs to flag in planner verification:** Phase 0 integration test must prove the unique constraint raises on a duplicate INSERT attempt.

### P4: Schema Drift Between Pydantic and Postgres

**What goes wrong:** Hand-maintained Pydantic models diverge from Postgres; worker inserts succeed but values land in wrong columns.

**How Phase 0 addresses it:** Codegen drift gate (Pattern 6). `datamodel-code-generator` regenerates `worker/workers/lib/models.py`; `drizzle-kit pull` regenerates `web/db/schema.ts`. CI runs `git diff --exit-code` after both.

**Warning sign during planning:** Any plan task that says "manually update Pydantic model" — should never appear.

### P7: Cost Cap Drift (schema groundwork only in Phase 0)

**What goes wrong:** Local cost tally diverges from provider invoice; cap never trips.

**How Phase 0 addresses it:** `budget_ledger` + `api_keys` tables ship with columns for `monthly_cap_cents`, `running_total_cents`, `provider_truth_cents`. Reconciliation logic lands in Phase 2; Phase 0 just guarantees the columns exist.

### P10: PII Boundary Leak via Upload Parser

**What goes wrong:** Upload accepts arbitrary CSV columns; non-allowlisted columns flow into Perplexity prompts; compliance breach.

**How Phase 0 addresses it:** D-00-10 — `app_config` row stores allowed source-column header set. Stub upload-parse function rejects out-of-allowlist headers with a clear error. Unit-tested against the two reference Run input files in `business_checker/Runs/`.

**Warning sign during planning:** Upload parse plan should hardcode no column names; everything comes from the `app_config` row.

### P11: pgmq Visibility-Timeout Misconfigured

**What goes wrong:** Worker holds a job > vt; second worker pulls the same message; double-billing.

**How Phase 0 addresses it:** D-00-09 — vt=300s set at the consumer call site (`read_with_poll(vt=300, ...)`), not at queue create time (which is silently ignored in tembo-pgmq-python 0.10). Phase 0 doesn't have long jobs yet, but the dispatcher stub already uses the correct call pattern.

### P12: Realtime Cross-User Leak (RLS doesn't auto-apply)

**What goes wrong:** Wildcard channel names + Realtime RLS not enabled → users see each other's runs.

**How Phase 0 addresses it:** Realtime publication membership is NOT added in Phase 0 (no live progress UI yet). When Phase 1 adds Realtime, RLS-for-Realtime must be enabled in the same migration. **Planner note:** Phase 0 should explicitly NOT add `verifications` or `run_rows` to `supabase_realtime` publication. Setting it up wrong here cascades.

## Code Examples

All authoritative code examples are inline above in §Architecture Patterns. Cross-references:

- Domain allowlist (middleware + RLS): Pattern 1
- Append-only triggers + UNIQUE constraints: Pattern 2
- Generic audit_log trigger: Pattern 3
- pgmq long-poll (worker): Pattern 4
- Worker heartbeat: Pattern 5
- Codegen drift gate (GitHub Actions): Pattern 6
- Eval-CI regression gate (GitHub Actions): Pattern 7

Additional reference points:

- **Supabase `@supabase/ssr` 0.10.x server client setup** — `https://supabase.com/docs/guides/auth/server-side/nextjs` (canonical; verified pattern in Pattern 1).
- **tembo-pgmq-python 0.10 API** — `https://github.com/tembo-io/pgmq/tree/main/tembo-pgmq-python` README (verify exact `read_with_poll` signature at implementation time; STACK.md cites 0.10.0 release notes as the source for `read_with_poll` + `set_vt`).
- **datamodel-code-generator postgres input** — `https://docs.pydantic.dev/datamodel-code-generator/` flags `--input-file-type postgres --url $DATABASE_URL --output-model-type pydantic_v2.BaseModel`.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `@supabase/auth-helpers-nextjs` | `@supabase/ssr` 0.10.x | Deprecated 2024; replacement stable through Next 14–16 | Use `createServerClient` / `createBrowserClient`; do NOT install auth-helpers |
| Pages Router | App Router (Server Components, server actions) | Next 14+; Next 16 is App-Router-first | All Phase 0 routes use App Router conventions |
| psycopg2 | psycopg 3.3.x | psycopg2 in maintenance mode | sync + async + pool from same driver |
| `getSession()` from cookies in Server Components | `getUser()` (validates against auth server) | Supabase canonical guidance, dated by `@supabase/ssr` docs | Phase 0 middleware uses `getUser()` exclusively |
| Drizzle for migrations | Supabase CLI for migrations; Drizzle introspect-only | D-00-03 — locked decision based on STACK.md analysis | Drizzle's RLS DSL is incomplete; one source of truth wins |
| pgmq vt at create time | pgmq vt per-read | tembo-pgmq-python 0.10 (Mar 2025) | Configure vt at `read_with_poll` call, not queue creation |

**Deprecated / outdated patterns to NOT carry forward:**

- Tkinter desktop UI patterns — frozen at v1.0 (PROJECT.md). Phase 0 ignores entirely.
- `business_checker/cache/` SQLite cache — being replaced by Postgres canonical lookup in Phase 1. Phase 0 doesn't touch it.
- `business_checker/run_checker.py` ThreadPoolExecutor concurrency — being replaced by asyncio + pgmq in Phase 2. Phase 0 only verifies importability of `business_checker.tools.*`.

## Open Questions

1. **`business_checker/pyproject.toml` package name and version**
   - What we know: STATE.md says aggregator extraction is a precondition (v1.0 polish, NOT a Phase 0 deliverable).
   - What's unclear: Does the package currently install cleanly with `pip install -e .`? If `pyproject.toml` declares `name = "Business Checker"` (with space) or similar, the editable install from `worker/` will fail.
   - Recommendation: Phase 0 wave A includes a "verify `pip install -e ../business_checker` works in a clean venv" smoke test. If broken, add a minimal `pyproject.toml` fix as a Phase 0 task (this counts as continued v1.0 polish, acceptable per STATE.md).

2. **Eval scorer JSON output shape**
   - What we know: `business_checker/eval/score.py` exists; Phase 0 wires it into CI.
   - What's unclear: Does it currently emit `accuracy` and `n_examples` keys, or some other shape?
   - Recommendation: Planner should add a verification task — run the scorer once locally before drafting the GitHub Actions step; either accept the existing keys or land a minimal output-format shim (in `business_checker/eval/score.py`) as a separate small commit before the Phase 0 PR.

3. **Resend account creation timing**
   - What we know: D-00-11 item 6 requires the IT ticket filed in Phase 0; the actual DNS records are Phase 4 path-critical.
   - What's unclear: Does a Resend account need to exist before filing the IT ticket (to know which records to ask for)?
   - Recommendation: Yes — create the Resend account in Phase 0 (free tier), generate the DKIM/SPF/DMARC record set on the IVMF subdomain in the Resend dashboard, then file the IT ticket with the exact records IT must publish. Track ticket ID in STATE.md.

4. **GitHub Actions secrets for codegen drift**
   - What we know: `drizzle-kit pull` and `datamodel-codegen` both need `DATABASE_URL` for the dev Supabase project.
   - What's unclear: Whether to use the pooled connection string (port 6543) or direct (port 5432). For introspection, direct (5432) is safer — pooler has DDL limitations.
   - Recommendation: Use direct connection string (port 5432) as the `SUPABASE_DEV_DB_URL` GitHub Actions secret; document in the workflow comment.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node 22.x | `web/` build + drift gate | ✓ (assumed; Vercel default) | 22.x | Lock via `engines` in `web/package.json` |
| pnpm | `web/` package manager | ✓ (per Julian's stack) | 9.x | npm if pnpm unavailable in CI |
| Python 3.12 | `worker/` + eval-ci | ✓ | 3.12 | 3.11 acceptable |
| Supabase project (dev) | All schema work | ✓ (per CONTEXT.md D-00-02 — must be provisioned at Phase 0 start) | Postgres 17 | — |
| Supabase project (prod) | Production deploy | ✓ (per STATE.md preconditions) | Postgres 17 | — |
| Railway account + project | Worker deploy | ✓ (per STATE.md preconditions) | — | Fly.io equivalent |
| Vercel account + project | Web deploy | ✓ (assumed Julian's workspace) | — | Cloudflare Pages equivalent |
| GitHub Actions runner minutes | CI | ✓ free tier sufficient at this scale | — | — |
| Resend account | DNS ticket filing | ✗ — likely not created yet | — | Create free-tier account in Phase 0 wave E |
| IVMF subdomain on `*.syr.edu` | Resend DNS setup | ✗ blocked on IT | — | None — IT ticket IS the deliverable |
| Perplexity API key for eval | eval-ci workflow | ✓ (per STATE.md — rotation recommended due to repo cleanup) | — | None — eval-ci is mandatory for Phase 0 exit |

**Missing dependencies with no fallback:** None blocking Phase 0 entry. The IVMF subdomain DNS is Phase 4 path-critical, but Phase 0 only needs the ticket filed, which can happen independently of IT's actual work.

**Missing dependencies with fallback:** Resend account (just create it; <10 min).

**Action items for planner:**
- Confirm Supabase dev + prod projects exist (STATE.md says provisioned; verify).
- Rotate Perplexity API key per STATE.md note (separate key for `PERPLEXITY_API_KEY_EVAL`).
- Create Resend account in Phase 0 wave E.

## Validation Architecture

> `.planning/config.json` does not set `workflow.nyquist_validation` to false (file shows no override per `.planning/config.json` check; treat as enabled per agent spec).

### Test Framework
| Property | Value |
|----------|-------|
| Framework (web) | vitest (latest stable; pin in Wave 0) |
| Framework (worker) | pytest (already wired in `business_checker/tests/`; mirror in `worker/tests/`) |
| Framework (database integration tests) | pytest + psycopg direct connection to dev Supabase |
| Config file (web) | `web/vitest.config.ts` — Wave 0 creates |
| Config file (worker) | `worker/pyproject.toml` `[tool.pytest.ini_options]` — Wave 0 creates |
| Quick run command (web) | `pnpm --filter ./web test` |
| Quick run command (worker) | `pytest worker/tests -x` |
| Full suite command | `pnpm --filter ./web test && pytest worker/tests business_checker/tests` |
| Phase gate command | Above plus `bash .github/scripts/phase0-demo.sh` (a script that exercises D-00-11 items 1, 4, 5 against the dev Supabase project) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AUTH-01 | Magic-link login round-trip succeeds for `@syr.edu` | e2e (Playwright stub OR manual demo gate) | `pnpm --filter ./web test:e2e auth.spec.ts` | ❌ Wave 0 |
| AUTH-01 (negative) | Non-allowlisted domain blocked at middleware with 403 | integration | `pnpm --filter ./web test middleware.test.ts` | ❌ Wave 0 |
| AUTH-02 | Editing `app_config.email_domain_allowlist` row admits new domain on next request | integration | `pytest worker/tests/test_app_config.py::test_allowlist_extend` | ❌ Wave 0 |
| AUTH-03 | `app_metadata.role` claims propagated through middleware AND RLS | integration | `pytest worker/tests/test_rbac.py` | ❌ Wave 0 |
| AUTH-04 | UPDATE on `app_config` produces audit_log row with diff jsonb | integration (psycopg) | `pytest worker/tests/test_audit_log.py::test_app_config_update_writes_diff` | ❌ Wave 0 |
| CANON-03 | Normalize helpers correct for known inputs (BMSG sample) | unit | `pytest worker/tests/test_normalize.py` | ❌ Wave 0 |
| CANON-05 | `businesses` table accepts new canonical rows with required NOT NULLs | integration | `pytest worker/tests/test_businesses_schema.py` | ❌ Wave 0 |
| CANON-06 | `UPDATE verifications` raises SQLSTATE P0001 | integration | `pytest worker/tests/test_append_only.py::test_update_raises` | ❌ Wave 0 |
| CANON-06 | `DELETE verifications` raises SQLSTATE P0001 | integration | `pytest worker/tests/test_append_only.py::test_delete_raises` | ❌ Wave 0 |
| CANON-07 | Duplicate INSERT same `(run_id, row_index, pass)` raises 23505 | integration | `pytest worker/tests/test_append_only.py::test_unique_violation` | ❌ Wave 0 |
| CANON-07 | Duplicate INSERT same `(provider, request_hash)` on `api_calls` raises 23505 | integration | `pytest worker/tests/test_api_calls.py::test_unique_violation` | ❌ Wave 0 |
| CANON-08 | `verifications` schema has `provenance jsonb`, `method text NOT NULL` | schema introspection | `pytest worker/tests/test_verifications_schema.py` | ❌ Wave 0 |
| ANALYTICS-04 | Flipped label in `eval/gold.json` causes eval-ci workflow to fail | manual / CI | demo via PR | ❌ Wave 0 (PR-based, not local) |
| D-00-09 | Worker long-polls `q_verify` with vt=300 | integration | `pytest worker/tests/test_dispatcher.py::test_long_poll` | ❌ Wave 0 |
| D-00-11 item 5 | `worker_heartbeats` row written within 30s of worker start | integration | `pytest worker/tests/test_heartbeat.py` | ❌ Wave 0 |
| D-00-03 | CI fails if `web/drizzle/migrations/` is non-empty | CI workflow | check via PR | ❌ Wave 0 |
| D-00-11 item 2 | Codegen drift gate fails when migration adds a column without committing regen | CI workflow / manual demo | demo via PR | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pnpm --filter ./web test && pytest worker/tests -x` (fast: <60s once cached)
- **Per wave merge:** Full suite + the codegen-drift workflow run against the PR branch via GitHub Actions
- **Phase gate (before `/gsd:verify-work`):** Full suite green + manual run of the 6 D-00-11 demo items + ticket ID for Resend DNS captured in STATE.md

### Wave 0 Gaps

- [ ] `web/vitest.config.ts` — vitest configuration with `@/` path alias for `web/`
- [ ] `web/tests/middleware.test.ts` — exercises domain-allowlist 403 path with a mock Supabase auth response
- [ ] `worker/pyproject.toml` — `[tool.pytest.ini_options]` section + `worker/tests/conftest.py` with a fixture that yields a psycopg connection to dev Supabase (env-gated)
- [ ] `worker/tests/test_append_only.py` — covers CANON-06 + CANON-07
- [ ] `worker/tests/test_audit_log.py` — covers AUTH-04
- [ ] `worker/tests/test_dispatcher.py` — covers D-00-09 long-poll behavior
- [ ] `worker/tests/test_heartbeat.py` — covers D-00-11 item 5
- [ ] `worker/tests/test_normalize.py` — covers CANON-03
- [ ] `worker/tests/test_verifications_schema.py` + `test_businesses_schema.py` + `test_api_calls.py` — schema-shape assertions
- [ ] `worker/tests/test_rbac.py` — covers AUTH-03
- [ ] `worker/tests/test_app_config.py` — covers AUTH-02
- [ ] `.github/scripts/phase0-demo.sh` — exercise D-00-11 demo items 1/4/5 from CI manually
- [ ] Framework install for vitest: `pnpm --filter ./web add -D vitest @vitest/ui jsdom` (Wave 0)
- [ ] `pytest-asyncio` + `pytest-postgres` not required; psycopg sync interface suffices for assertions

## Sources

### Primary (HIGH confidence)
- `.planning/research/STACK.md` (2026-05-12) — pinned versions cross-verified against npm/PyPI on the same date
- `.planning/research/ARCHITECTURE.md` (2026-05-12) — topology, module layout, integration points
- `.planning/research/PITFALLS.md` (2026-05-12) — P1, P4, P7, P10, P11, P12 are Phase 0 prevention scope
- `.planning/research/SUMMARY.md` (2026-05-12) — build order and risk weighting
- `.planning/REQUIREMENTS.md` (2026-05-12) — AUTH-01..04, CANON-03/05/06/07/08, ANALYTICS-04 traceability
- `.planning/phases/00-foundation/00-CONTEXT.md` — locked decisions D-00-01..D-00-11

### Secondary (MEDIUM confidence — official docs cited indirectly via STACK.md)
- Supabase Auth Server-Side guide for Next.js App Router (`@supabase/ssr` 0.10.x) — `getUser()` vs `getSession()` canonical guidance
- Supabase Queues GA docs (pgmq) — extension availability + `pgmq.create()` SQL surface
- `tembo-pgmq-python` 0.10 release notes — `read_with_poll`, `set_vt`, per-read vt semantics
- `datamodel-code-generator` 0.57 — postgres input mode, pydantic v2 output flags
- Drizzle 0.45 — `drizzle-kit pull` introspection workflow
- Next.js 16 App Router middleware + server-actions docs

### Tertiary (LOW confidence — call out for verification at implementation time)
- Exact `read_with_poll` parameter names in tembo-pgmq-python 0.10 (verify with `help(PGMQueue.read_with_poll)` after install)
- Exact `audit_log_trigger()` behavior when `current_setting('app.request_id', true)` is unset — should return NULL per Postgres docs but verify on dev project
- Whether `drizzle-kit pull` writes `web/db/schema.ts` deterministically (column ordering) across runs — if not, drift gate may have false positives; mitigation is to canonicalize via `prettier` before `git diff`

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions cross-verified against npm + PyPI on 2026-05-12 in STACK.md
- Architecture patterns: HIGH — derived from CONTEXT.md locked decisions and ARCHITECTURE.md (already approved)
- Pitfalls: HIGH — PITFALLS.md catalog is comprehensive and Phase 0 scope is well-defined
- Codegen drift gate exact CI shape: MEDIUM — `drizzle-kit pull` determinism and `datamodel-codegen` output formatting may require a `prettier`/`black` canonicalization step (flagged in Open Question 4 and Tertiary sources)
- Eval scorer JSON shape: MEDIUM — needs verification at implementation time (Open Question 2)

**Research date:** 2026-05-12
**Valid until:** 2026-06-11 (30 days — stack is stable; reverify package versions if implementation slips past this date)
