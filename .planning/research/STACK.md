# Stack Research — v1.1 Web Platform Pivot

**Domain:** Hosted multi-tenant verification platform layered on top of an existing Python verification engine
**Researched:** 2026-05-12
**Confidence:** HIGH (versions verified against npm/PyPI registries on 2026-05-12; vendor-doc behavior verified against official sources)

**Scope:** ONLY additions/changes needed for v1.1. The existing Python engine in `business_checker/tools/` (check_business, scrape_website, aggregator, eval harness, SQLite cache, openpyxl XLSX export, pydantic 2.12, pandas 2.2, requests 2.33) is preserved as-is on the Railway worker. Do not re-research those.

---

## Recommended Stack — Additions

### Core Platform (NEW)

| Technology | Version (verified) | Purpose | Why over alternative |
|---|---|---|---|
| **Next.js** | `16.2.6` (npm latest, 2026-05-12) | UI + lightweight API routes on Vercel. App Router with React Server Components for the dashboard, upload, review, and admin pages. | App Router server actions cleanly call Supabase server-side; alternatives (Remix, SvelteKit) lose Vercel-native ISR/edge auth; Julian's preferred stack. **Pin major: 16.x.** |
| **React** | `19.2.6` | Pinned by Next 16. Server Components default. | n/a — bundled with Next. |
| **Supabase Postgres** | Platform (Postgres 17 underlying) | Single source of truth: schema, RLS, Realtime, pgmq, Storage. | Alternative (Neon + Clerk + Inngest + S3) = 4 vendors, more glue, no pg_trgm wired to RLS out of the box. Single-vendor cuts auth+realtime+queue integration risk. |
| **Supabase Auth** | bundled | Two-role RBAC (admin/user) via `auth.users` + a `profiles.role` enum and RLS policies. | Clerk/Auth0 add cost + a second user table to keep in sync with RLS-aware Postgres rows. |
| **pgmq** (Postgres extension) | `1.5.x` shipped by Supabase Queues (GA) | Durable job queue for verification runs. Visibility-timeout messages give exactly the resumability the v1.0 desktop checkpoint provided. | SQS = cross-vendor, no RLS, no transactional enqueue with DB writes. Inngest = vendor lock + costs scale with jobs. BullMQ = needs Redis. Native Postgres queue = transactional enqueue with the `runs` row insert, single backup story. |
| **pg_cron** (Postgres extension) | bundled (Supabase) | Periodically poll pgmq for stuck/expired heartbeats, fire weekly eval-drift checks, sweep abandoned runs. | External scheduler (GitHub Actions cron, Vercel Cron) works but adds a second failure point; pg_cron lives inside the DB and survives platform restarts. |
| **pg_trgm + fuzzystrmatch** | bundled (Supabase) | Canonical business matching (name similarity, Levenshtein on city/state). Powers 2-of-N field consensus rule. | Algolia/Typesense = external index sync; pg_trgm runs inside the same query that reads `businesses` with RLS, no sync window. |
| **Railway** | platform | Long-running Python FastAPI worker. Pulls pgmq messages, runs existing `check_business.py` + `scrape_website.py`. | Vercel/Lambda timeouts (15 min hard cap) cannot hold a 50k-row Perplexity run that takes hours. Fly.io is equivalent; Railway chosen for simpler deploy UX. **Do NOT use Supabase Edge Functions for the worker — Deno + 400s wall-time cap.** |
| **Resend** | `6.12.3` (npm) | Transactional email: outreach to businesses, run-completion receipts. | Postmark is the only serious peer; Resend chosen for React Email integration, simpler DKIM setup, lower minimum cost. Decision is reversible (both use SMTP/REST). |
| **Vercel** | platform | Frontend + Next.js API routes hosting. | Already paired with Next.js; no real alternative once Next is chosen. |

### Supporting Libraries — Next.js side

| Library | Version (verified) | Purpose | When to use |
|---|---|---|---|
| `@supabase/supabase-js` | `2.105.4` | Browser + server SDK to Supabase. | All client-side reads + Realtime subscriptions. |
| `@supabase/ssr` | `0.10.3` | Cookie-bound auth in Next.js App Router. | Required pattern for Server Components reading `auth.uid()`. **See anti-patterns below.** |
| `zod` | `4.4.3` | Schema validation at every API/server-action boundary. | Validate CSV upload metadata, outreach form submissions, admin edits. |
| `drizzle-orm` | `0.45.2` | SQL schema-as-code + migrations + TS types from Postgres. | Owns migrations; Supabase CLI handles RLS/policies, Drizzle owns table DDL. **See ORM decision below.** |
| `drizzle-kit` | matches drizzle-orm minor | Migration CLI. | Dev-time only. |
| `react-hook-form` + `@hookform/resolvers` | latest stable | Forms (upload, outreach response, admin edit). | Standard pairing with Zod. |
| `@tanstack/react-table` | v8 latest | Run-rows grid, review queue, admin DB editor. | Domain-fit for 50k-row tables with virtualization. |
| `tailwindcss` | `4.3.0` | Styling. | Tailwind v4 ships with Next 16; no PostCSS config needed. |
| `react-email` + `@react-email/components` | latest stable | Outreach + receipt templates rendered to HTML for Resend. | Resend's first-class template story. |
| `papaparse` | `5.x` | Client-side CSV preview before upload. | Upload validation in the browser. Server-side parsing happens in Python. |

### Supporting Libraries — Python worker side (NEW; on top of existing engine)

| Library | Version (verified) | Purpose | Why |
|---|---|---|---|
| `fastapi` | `0.136.1` | HTTP surface for the worker (health, manual trigger, eval webhook). | Standard. The actual job loop is a background asyncio task, not request-bound. |
| `uvicorn[standard]` | `0.35.x` (latest stable) | ASGI server. | Standard FastAPI pairing. |
| `psycopg[binary,pool]` | `3.3.4` (2026-05-01) | Postgres driver. Sync + async, connection pooling, COPY support. | psycopg3 is now the default; asyncpg lacks type-safe COPY and is harder to share between sync (existing engine) and async (queue loop) code paths. **Do NOT use psycopg2 — EOL track.** |
| `tembo-pgmq-python` | `0.10.0` (Mar 2025) | Python client for pgmq (read/archive/delete messages, set visibility timeout). | Official client from pgmq maintainers. Verified: handles long visibility timeouts + heartbeat extension which the worker needs. |
| `tenacity` | `9.1.4` (Feb 2026) | Retry/backoff on Perplexity 429/500/timeout and FireCrawl transient errors. | Decorator API is cleaner than `backoff`; supports async + sync; integrates with the existing engine's call sites with minimal change. |
| `httpx` | `0.28.1` | Async HTTP client where needed (Resend webhooks, outreach token verification callbacks). | Existing engine uses `requests==2.33` for Perplexity — keep that. Add httpx only for new async paths. |
| `supabase` (Python SDK) | `2.30.0` | Storage uploads (XLSX export to Supabase Storage), auth admin calls if needed. | Convenience wrapper. **Do not use it for queries** — psycopg + Drizzle-generated schema is the path. |
| `python-multipart` | latest | FastAPI form/file uploads (manual trigger endpoints). | Standard. |
| `structlog` | `25.x` latest | Structured logs with run_id correlation. | Required for the audit/observability constraint. |
| `pydantic` | `2.12.5` (already pinned) | Models. Already in use; v1.1 keeps it. | n/a |

### Address normalization (specifically called out)

| Choice | Verdict | Reasoning |
|---|---|---|
| **`usaddress` (PyPI 0.5.16, Aug 2025)** | **RECOMMENDED for v1.1** | Pure-Python, no system deps, MIT, US-only (matches IVMF dataset). Parses into structured components reliably for the 2-of-N canonical match. Install via `pip install usaddress`. |
| `postal` (Python binding for libpostal) | NOT RECOMMENDED for v1.1 | Requires building libpostal from C source on Railway (≈2GB model files, complex Docker layer). Worth it only if the data goes international. IVMF data is US-only. |
| Google Places API | NOT RECOMMENDED for canonical matching | Per-call cost, rate limits, and pushes more PII to a third party. Reserve as a **future** option for high-value disambiguation only. |
| `scourgify` | Optional | USPS-style normalization on top of usaddress output. Add only if 2-of-N is too noisy. |

### Type-safe model generation (specifically called out)

**Decision: Drizzle (TS) + datamodel-code-generator (Python), both reading from Supabase Postgres as source of truth.**

| Side | Tool | Version | How |
|---|---|---|---|
| TypeScript (Next.js) | `drizzle-kit introspect` → `drizzle-orm` types | `0.45.2` | Pulls live schema from Supabase Postgres into `db/schema.ts`. Generates exact-shape TS types automatically. Also runs migrations. |
| Python (worker) | `datamodel-code-generator` | `0.57.0` (Jan 2025) | `datamodel-codegen --input-file-type postgres --url $DATABASE_URL --output models.py` produces pydantic v2 models matching the live schema. Run in CI; commit the generated file. |
| (alternative for TS only) | `supabase gen types typescript` | bundled CLI | Use ALONGSIDE Drizzle for the Supabase JS client (RLS-aware row types). Drizzle owns table shape; this owns the `Database` generic for `createClient<Database>`. |

**ORM decision rationale:**
- **Drizzle over Prisma:** Drizzle generates SQL you can read, supports Postgres-native features (jsonb, generated columns, RLS-friendly raw SQL escape hatches) that Prisma still wraps poorly. Smaller bundle on Vercel. Migrations are plain SQL files reviewable in PR.
- **Drizzle over raw SQL:** Type safety on the read path is critical for a 30+ table schema. Raw SQL via `postgres.js` is fine for the worker but Next.js benefits hugely from compile-time column-name checks.
- **Migrations:** Drizzle owns table DDL. **Supabase CLI (`supabase migration new`) owns RLS policies, functions, triggers, and pg_cron schedule**, because Drizzle's RLS DSL is incomplete as of 0.45. Two migration directories, one source of truth (`supabase/migrations/`) wins.

---

## Installation

```bash
# Next.js project (apps/web)
pnpm create next-app@16 web --typescript --tailwind --app --no-src-dir
cd web
pnpm add @supabase/supabase-js@2.105.4 @supabase/ssr@0.10.3 \
         zod@4.4.3 react-hook-form @hookform/resolvers \
         @tanstack/react-table papaparse \
         resend@6.12.3 react-email @react-email/components \
         drizzle-orm@0.45.2 postgres
pnpm add -D drizzle-kit@0.45 supabase @types/papaparse

# Python worker (apps/worker)
# Inherits existing business_checker/requirements.txt unchanged. Add:
pip install fastapi==0.136.1 'uvicorn[standard]' \
            'psycopg[binary,pool]==3.3.4' \
            tembo-pgmq-python==0.10.0 \
            tenacity==9.1.4 \
            httpx==0.28.1 \
            supabase==2.30.0 \
            python-multipart structlog \
            usaddress==0.5.16

# Dev-time only
pip install datamodel-code-generator==0.57.0
```

---

## Alternatives Considered

| Recommended | Alternative | When alternative wins |
|---|---|---|
| pgmq | AWS SQS | If IVMF mandates non-Supabase queue. Loses transactional enqueue. |
| pgmq | Inngest / Trigger.dev | If multi-step workflow DAGs explode in complexity. Currently a single linear job per row — overkill. |
| pgmq | BullMQ + Redis | If sub-100ms job pickup matters. It doesn't — Perplexity calls are seconds. |
| pg_trgm + fuzzystrmatch | Algolia/Typesense | If Julian wants typeahead search UX on the businesses table. Defer to v1.2. |
| pg_trgm | Postgres full-text + `unaccent` | For longer free-text descriptions. Business names are short — trigram is the right tool. |
| usaddress | libpostal (`postal`) | International addresses or non-Latin scripts. IVMF data is US — not now. |
| Resend | Postmark | If deliverability scoring is a deal-breaker. Both have equivalent SPF/DKIM/DMARC stories. |
| Resend | AWS SES | If IVMF already has an AWS billing relationship. SES requires more setup. |
| Drizzle | Prisma | If team grows past Julian and a more guided DSL helps onboarding. |
| Drizzle | Raw SQL via `postgres.js` | If schema stays small (<10 tables). It won't — schema already implies ~15 tables. |
| psycopg3 | asyncpg | Pure async path with no sync calls. We have sync engine code reusing the same connection pool — psycopg3's sync+async same-driver story wins. |
| Railway | Fly.io | Equivalent. Choose by deploy UX preference. |
| Railway | Render | Equivalent. |
| Next.js App Router | Pages Router | Never — App Router is the supported path going forward. |

---

## What NOT to Use (Anti-Patterns)

| Avoid | Why | Use Instead |
|---|---|---|
| **Supabase Edge Functions for the verification worker** | Deno runtime, 400-second wall-time cap, no long-running asyncio loop, can't reuse the existing Python engine. | **Railway-hosted Python FastAPI worker.** |
| **Vercel serverless functions for verification** | 15-minute max (Pro), incompatible with hours-long runs. | Same — Railway worker. |
| **`@supabase/ssr` `getSession()` in Server Components** | Tokens can be tampered; the cookie alone isn't authenticated against the auth server. | Use **`supabase.auth.getUser()`** in Server Components and middleware (this hits the auth server and is verified). [Documented Supabase guidance.] |
| **`@supabase/auth-helpers-nextjs`** | Deprecated by Supabase. | `@supabase/ssr@0.10.3`. |
| **psycopg2** | Maintenance mode; psycopg3 is the future. | `psycopg[binary,pool]==3.3.4`. |
| **`supabase-py` for table queries from the worker** | Wraps PostgREST; adds a network hop the worker doesn't need (it has direct DB credentials). | psycopg3 direct queries + Drizzle-mirrored Python pydantic models. |
| **Storing API keys (Perplexity, FireCrawl, Resend) in app DB columns** | Plain-text secrets in `app_settings` is a leak waiting to happen. | Railway env vars + Supabase Vault for rotation. Admin UI shows masked values only. |
| **Polling `verifications` for progress updates from the browser** | Hammers the DB at 50k rows. | **Supabase Realtime channel keyed by `run_id`** with batched progress events (1/sec aggregate, not per-row). |
| **`git add .` for Supabase migrations** | `.supabase/` artifacts and `supabase/.temp/` leak into commits. | `git add supabase/migrations/*.sql` only. |
| **Letting the worker write directly to `business_current_state`** | Race conditions across multiple workers. | Worker writes append-only to `verifications`; a Postgres trigger or scheduled function projects into `business_current_state`. |
| **Resend `from: julian@gmail.com`** | DMARC will reject — must be on a verified IVMF subdomain. | `from: outreach@<ivmf-subdomain>.syr.edu` (or equivalent) after DNS records are in. Required: SPF TXT, DKIM CNAME (3 records), DMARC TXT. |
| **Pydantic v1 in the worker** | Existing engine already uses v2 (`pydantic==2.12.5`). Mixing breaks fastapi 0.136. | Stay on Pydantic v2 everywhere. |
| **`@supabase/realtime-js` from the worker** | Worker has direct DB access; doesn't need to round-trip through Realtime. | Worker writes rows; Realtime fans out to subscribers automatically. |

---

## Stack Patterns by Variant

**If IVMF mandates on-prem / non-Supabase hosting (out of scope per PROJECT.md, but reversible):**
- Replace Supabase with self-hosted Postgres 16+ + Hasura/PostgREST + Authelia.
- pgmq, pg_trgm, pg_cron all work on vanilla Postgres — schema is portable.
- Resend can be swapped for Postmark or local SMTP.

**If a second IVMF team wants their own data isolation later (currently out of scope):**
- Add a `tenant_id` column on every table + RLS predicate. Schema is already multi-tenant-shaped via `user_id` on `runs`. Migration is mechanical.

**If outreach response volume requires a queue:**
- Reuse pgmq with a separate queue name (`outreach_responses`). No new infra.

---

## Version Compatibility Notes

| Package A | Compatible With | Notes |
|---|---|---|
| Next.js 16.x | React 19.x | Required pair. |
| `@supabase/ssr@0.10.x` | Next.js 14–16 App Router | Cookie API stable. |
| Tailwind 4.x | Next.js 16, PostCSS-free | Native CSS-first config. Old `tailwind.config.js` migration required if porting from v3. |
| psycopg 3.3.x | Python ≥ 3.10 | Worker is Python 3.11+ already — fine. |
| Pydantic 2.12 | FastAPI 0.136 | Compatible. |
| Drizzle 0.45 | Postgres 13+ | Supabase is Postgres 17. Fine. |
| pgmq (Supabase Queues) | Postgres 14+ | GA on Supabase platform. |
| `tembo-pgmq-python@0.10.0` | pgmq 1.x | Maintainer-provided client. |
| `usaddress@0.5.16` | Python 3.9+ | Fine. |

---

## Configuration: Resend DNS (called out for Phase 4 roadmap consumer)

For the IVMF subdomain that will send outreach mail, IT must add (Resend dashboard generates exact values):

1. **SPF** — TXT record: `v=spf1 include:_spf.resend.com -all` on the sending subdomain.
2. **DKIM** — 3 CNAME records (`resend._domainkey`, `resend2._domainkey`, `resend3._domainkey`) pointing to Resend-provided targets.
3. **DMARC** — TXT record at `_dmarc.<subdomain>`: start with `v=DMARC1; p=none; rua=mailto:dmarc@<subdomain>` (monitor mode), tighten to `p=quarantine` after 2 weeks of clean reports.
4. **MX (optional)** — only if accepting replies; route to a shared inbox or Resend Inbound.

DNS propagation is the path-critical item on Phase 4. Open the IT ticket at Phase 0.

---

## Sources

- npm registry — verified 2026-05-12 — `next@16.2.6`, `@supabase/supabase-js@2.105.4`, `@supabase/ssr@0.10.3`, `resend@6.12.3`, `drizzle-orm@0.45.2`, `zod@4.4.3`, `react@19.2.6`, `tailwindcss@4.3.0`. Confidence: HIGH.
- PyPI — verified 2026-05-12 — `fastapi@0.136.1`, `psycopg@3.3.4` (2026-05-01), `tenacity@9.1.4` (2026-02-07), `httpx@0.28.1`, `supabase@2.30.0`, `tembo-pgmq-python@0.10.0`, `usaddress@0.5.16`, `datamodel-code-generator@0.57.0`. Confidence: HIGH.
- Supabase docs (`supabase.com/docs/guides/queues`) — pgmq is the backing extension for Supabase Queues. Confidence: HIGH on availability; MEDIUM on long-term version cadence (Supabase platform manages the upgrade).
- Supabase auth docs — `getUser()` vs `getSession()` distinction in Server Components is canonical guidance. Confidence: HIGH.
- Existing project files — `business_checker/requirements.txt`, `business_checker/pyproject.toml` for current engine pins. Confidence: HIGH.

---
*Stack research for: IVMF Business Checker v1.1 Web Platform Pivot*
*Researched: 2026-05-12*
