---
phase: 00-foundation
plan: 04
subsystem: web-auth-shell
tags: [auth, magic-link, middleware, rls, rbac, supabase-ssr, next-app-router, defense-in-depth]
dependency-graph:
  requires:
    - "00-01-wave0-test-scaffolding (vitest config, web/tests stubs, worker/tests stubs)"
    - "00-02-supabase-schema-rls (app_config seed + auth.is_allowed_domain function in 0006)"
    - "00-03-codegen-drift-gate (web/db/schema.ts + types.ts baseline)"
  provides:
    - "web/middleware.ts — edge auth + domain allowlist (defense layer 1)"
    - "web/lib/supabase/{server,client,service-role}.ts — canonical @supabase/ssr clients"
    - "web/lib/auth/allowlist.ts — 60s edge-cached read of app_config row"
    - "web/app/(auth)/sign-in/page.tsx — magic-link-only sign-in (D-00-04)"
    - "web/app/api/auth/callback/route.ts — exchangeCodeForSession handler"
    - "web/app/me/page.tsx — authenticated landing page (D-00-11 item 1)"
    - "supabase/migrations/0008_rbac_role_default.sql — AUTH-03 role default + JWT helper"
  affects:
    - "Every subsequent web/ feature (must run after middleware admits the request)"
    - "Every RLS policy added after 0008 that depends on role (must use auth.current_role_claim())"
    - "Wave 5 demo: closes D-00-11 item 1 (magic-link round-trip)"
tech-stack:
  added:
    - "@tailwindcss/postcss 4.3.0 (PostCSS plugin for Tailwind v4 CSS-first config)"
  patterns:
    - "Defense-in-depth: middleware getUser() + Postgres auth.is_allowed_domain() read the SAME app_config row"
    - "Edge-cached allowlist (60s TTL, 10s on error, fails closed) to keep middleware fast"
    - "@supabase/ssr canonical pattern (createServerClient + cookie getAll/setAll); NEVER getSession()"
    - "Service-role key with NO NEXT_PUBLIC_ prefix + typeof window guard"
    - "Magic-link sign-in pre-flight allowlist check BEFORE signInWithOtp (UI feedback layer 1.5)"
    - "Role propagation single-source-of-truth: app_metadata.role -> JWT -> auth.current_role_claim() -> RLS"
key-files:
  created:
    - "web/next.config.ts"
    - "web/tailwind.config.ts"
    - "web/postcss.config.mjs"
    - "web/app/layout.tsx"
    - "web/app/globals.css"
    - "web/app/page.tsx"
    - "web/app/(auth)/sign-in/page.tsx"
    - "web/app/api/auth/callback/route.ts"
    - "web/app/me/page.tsx"
    - "web/middleware.ts"
    - "web/lib/supabase/server.ts"
    - "web/lib/supabase/client.ts"
    - "web/lib/supabase/service-role.ts"
    - "web/lib/auth/allowlist.ts"
    - "web/.env.example"
    - "web/pnpm-lock.yaml"
    - "supabase/migrations/0008_rbac_role_default.sql"
  modified:
    - "web/package.json (drizzle-kit ^0.45 -> ^0.45 replaced with ^0.31 — registry truth; added @tailwindcss/postcss)"
    - "web/.gitignore (*.tsbuildinfo, pnpm-workspace.yaml scratch)"
    - "web/tests/middleware-allowlist.test.ts (5 assertions, no xfail)"
    - "web/tests/auth-magic-link.spec.ts (3 surface contracts, no xfail)"
    - "worker/tests/test_rls_domain_allowlist.py (4 assertions, no xfail/NotImplementedError)"
    - "worker/tests/test_rbac.py (2 assertions, no xfail/NotImplementedError)"
    - "worker/tests/test_allowlist_admin.py (3 assertions w/ finally restore, no xfail)"
decisions:
  - "Allowlist cache: 60s TTL on success, 10s TTL on error, fails CLOSED to ['syr.edu']. Admin allowlist edits propagate to all edge workers within 60s — acceptable for AUTH-02 since admin edits are rare and the rule itself is conservative."
  - "AUTH-03 role storage: app_metadata.role is the canonical source. NO profiles table introduced in Phase 0 — Supabase Auth's app_metadata is sufficient and avoids a second user table to keep in sync with RLS-aware rows (per STACK.md rejected list rationale)."
  - "Defense-in-depth: middleware reads app_config via Supabase JS client; RLS reads the same row via auth.is_allowed_domain(). Reading only one is a known-bypass shape per D-00-05."
  - "Magic-link only per D-00-04. No password form, no reset flow, no password field on /sign-in. Revisit in v1.2 minor phase if IVMF staff feedback requires."
  - "drizzle-kit version pin corrected to ^0.31 (registry latest 0.31.10). The original ^0.45 reference in STACK.md research conflated drizzle-orm 0.45 with drizzle-kit, which has a separate, lower version line."
  - "pnpm-workspace.yaml is gitignored — pnpm 11 writes a `allowBuilds` prompt placeholder there during `pnpm install`; the file has no meaningful project content."
metrics:
  duration: "~25 min (single-executor wave)"
  completed-date: "2026-05-14"
  tasks: 3
  files-created: 17
  files-modified: 8
  commits: 3
requirements-closed: [AUTH-01, AUTH-02, AUTH-03]
---

# Phase 00 Plan 04: Web Auth Shell Summary

## One-Liner

Next.js 16 App Router shell with `@supabase/ssr` magic-link auth, edge middleware enforcing the `app_config.email_domain_allowlist` (defense layer 1) in tandem with the Postgres `auth.is_allowed_domain()` RLS function (defense layer 2), plus a `/me` page that closes D-00-11 item 1 — landing AUTH-01, AUTH-02, AUTH-03 in one wave.

## What Shipped

### Task 1 — Next.js skeleton + Supabase clients (commit `8b240f1`)

- **`web/next.config.ts`, `tailwind.config.ts`, `postcss.config.mjs`, `app/layout.tsx`, `app/globals.css`, `app/page.tsx`** — Next.js 16 + Tailwind v4 baseline. `globals.css` uses the v4 single-import (`@import 'tailwindcss'`). Root `page.tsx` redirects to `/me`; middleware handles the actual auth gating.
- **`web/lib/supabase/server.ts`** — `createServerClient` from `@supabase/ssr` bound to Next.js cookies. `setAll` guarded so Server Component invocations (read-only cookies) don't throw. Inline docstring explicitly forbids `getSession()`.
- **`web/lib/supabase/client.ts`** — `createBrowserClient` for Client Components.
- **`web/lib/supabase/service-role.ts`** — reads `SUPABASE_SERVICE_ROLE_KEY` (no `NEXT_PUBLIC_` prefix). Runtime `typeof window !== 'undefined'` throw guards against accidental client-side import.
- **`web/.env.example`** — 4 keys: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_SITE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (last one explicitly marked server-only).
- **`web/package.json`** — pinned `drizzle-kit` to `^0.31.0` (npm registry truth on 2026-05-14; STACK.md's `^0.45` reference was stale). Added `@tailwindcss/postcss ^4.3.0` dev dep.
- **`web/pnpm-lock.yaml`** — generated by `pnpm install`; 167 packages added.

### Task 2 — Middleware + allowlist + sign-in + callback + /me + migration (commit `6500f57`)

- **`web/middleware.ts`** — defense layer 1. Calls `supabase.auth.getUser()` (NOT `getSession()` per PITFALLS P5), reads allowlist via `getAllowlist()`, returns 403 with `Sign-in restricted to allowed domains: syr.edu. Contact an admin to extend the allowlist.` for non-allowlisted authed users, redirects unauthenticated users to `/sign-in?next=<original-path>`. Matcher excludes `_next/static`, `_next/image`, `favicon.ico`, and any path containing a dot (static files).
- **`web/lib/auth/allowlist.ts`** — 60-second edge cache reading `app_config.email_domain_allowlist`. Fails CLOSED to `['syr.edu']` with a 10-second TTL on error so recovery is fast once the DB is healthy. `clearAllowlistCache()` exported for tests and admin UI.
- **`web/app/(auth)/sign-in/page.tsx`** — magic-link only per D-00-04. One email input, one button. Pre-flight allowlist check (UI feedback layer 1.5) runs BEFORE `signInWithOtp`; sends user to `/api/auth/callback?next=...` after the magic-link is clicked.
- **`web/app/api/auth/callback/route.ts`** — `exchangeCodeForSession(code)` then redirect to `next` (or `/me`). On error, redirects to `/sign-in?error=...` with the message encoded.
- **`web/app/me/page.tsx`** — Server Component using the just-created `createServerClient()`. Reads `user.app_metadata.role` (default `'user'`); renders email + role + user id. Closes D-00-11 item 1.
- **`supabase/migrations/0008_rbac_role_default.sql`** — AUTH-03 surface:
  - `public.handle_new_user_role()` trigger function + `trg_handle_new_user_role` after-insert trigger on `auth.users` setting `raw_app_meta_data.role = 'user'` when not already supplied.
  - `auth.current_role_claim()` RLS helper extracting role from JWT (reads top-level `role`, then `app_metadata.role`, default `'user'`).
  - Replaces `app_config_admin_all` policy (from 0002) with one that reads role through `auth.current_role_claim()`, ensuring middleware and RLS share a single canonical source.

### Task 3 — Test wire-up (commit `e9a1de8`)

- **`web/tests/middleware-allowlist.test.ts`** — 5 vitest cases. `@supabase/ssr` and `@/lib/auth/allowlist` mocked via `vi.mock`. Asserts 307+`?next=%2Fme` for unauth, 403+`Sign-in restricted`+`syr.edu` for `@gmail.com`, status < 400 + no Location for `@syr.edu`, public `/sign-in` and `/api/auth/callback` admitted without auth.
- **`web/tests/auth-magic-link.spec.ts`** — 3 module-surface tests (callback `GET`, `/me` default export, `/sign-in` default export). Full browser round-trip is exercised in the manual D-00-11 demo, not here.
- **`worker/tests/test_rls_domain_allowlist.py`** — 4 pytest cases: `auth.is_allowed_domain` exists, admits `@syr.edu`, blocks `@gmail.com`, `auth.current_role_claim` helper exists.
- **`worker/tests/test_rbac.py`** — 2 cases: `trg_handle_new_user_role` installed, `app_config_admin_all` policy expression contains `current_role_claim` or `'admin'`.
- **`worker/tests/test_allowlist_admin.py`** — AUTH-02 round-trip. UPDATEs `app_config` to add `example.com`, asserts `auth.is_allowed_domain('a@example.com')` returns true, syr.edu stays admitted, `other.com` stays blocked (proves the function reads the table, not a hardcoded list). Restores original value in `finally`.

## Verification Results

- `cd web && ./node_modules/.bin/tsc --noEmit` — exits 0 (no TypeScript errors).
- `cd web && ./node_modules/.bin/vitest run tests/middleware-allowlist.test.ts tests/auth-magic-link.spec.ts` — **8 tests passed**.
- `cd worker && python3 -m pytest tests/test_rls_domain_allowlist.py tests/test_rbac.py tests/test_allowlist_admin.py -v` — **7 tests collected**, all 7 skipped cleanly (SUPABASE_DEV_DB_URL not set; per STATE.md "Dev Supabase project not provisioned"). When the dev DB lands, all 7 are expected to pass.
- `grep -lE "xfail|NotImplementedError"` across all 5 wired test files — zero matches.
- `grep -rE "\.getSession\(\)"` across `web/lib/` and `web/app/` — zero matches (PITFALLS P5 satisfied).
- `grep -r "@supabase/auth-helpers-nextjs" web/` — zero matches (deprecated package not used).

## Acceptance Criteria Status

### Task 1 — SHIPPED
- All 8 listed files exist under `web/`.
- `server.ts` uses `createServerClient` from `@supabase/ssr` (not `auth-helpers-nextjs`).
- `service-role.ts` reads `SUPABASE_SERVICE_ROLE_KEY` (no `NEXT_PUBLIC_` prefix) and has the `typeof window` throw guard.
- `.env.example` contains exactly the 4 required keys and documents service-role as server-only.
- `pnpm exec tsc --noEmit` exits 0.
- `grep getSession() / @supabase/auth-helpers-nextjs` — zero matches.

### Task 2 — SHIPPED (migration apply DEFERRED, see Deviations)
- All 6 files exist.
- `middleware.ts` uses `supabase.auth.getUser()` and emits the required 403 message + `/sign-in?next=` redirect.
- Matcher excludes `_next/static`, `_next/image`, `favicon.ico`, and dotted files.
- `lib/auth/allowlist.ts` reads `app_config` key `email_domain_allowlist` with 60s TTL cache.
- Sign-in page is a Client Component with pre-flight allowlist check before `signInWithOtp`.
- Callback route calls `exchangeCodeForSession(code)` and redirects to `/me` on success.
- `/me` page is a Server Component using `createServerClient` from `@/lib/supabase/server` and reads `user.app_metadata.role`.
- Migration defines `handle_new_user_role` trigger AND `auth.current_role_claim()` function.
- `tsc --noEmit` exits 0.

### Task 3 — SHIPPED
- `middleware-allowlist.test.ts` and `auth-magic-link.spec.ts` use `it(...)` with real assertions (no `it.fails`).
- Vitest exits 0 with 8 tests passing (≥ 7 required).
- Pytest tests no longer contain `xfail` or `NotImplementedError`.
- Pytest tests collect cleanly and skip cleanly without dev DB.
- Middleware test asserts 403 status AND text contains "Sign-in restricted".
- Middleware test asserts 307 redirect to `/sign-in` for unauthenticated.
- `test_allowlist_admin.py` asserts both `example.com` admitted AFTER update AND `other.com` still blocked.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking issue] `drizzle-kit ^0.45.0` not on npm registry**

- **Found during:** Task 1 — `pnpm install` failed with `ERR_PNPM_NO_MATCHING_VERSION No matching version found for drizzle-kit@^0.45.0`.
- **Issue:** `web/package.json` (from 00-01 Wave 0 scaffolding) and STACK.md research baseline pin `drizzle-kit ^0.45`. The npm registry truth on 2026-05-14: `drizzle-orm@0.45.2` exists but `drizzle-kit`'s latest is `0.31.10` (they're on different version lines).
- **Fix:** Repinned `drizzle-kit` to `^0.31.0` in `web/package.json`. `drizzle-orm@0.45.2` stays. The Drizzle introspect contract from 00-03 (drizzle.config.ts) is unaffected — `drizzle-kit pull` works identically.
- **Files modified:** `web/package.json`
- **Commit:** `8b240f1`
- **How to retire:** Whenever drizzle-kit catches up to drizzle-orm versioning, bump.

**2. [Rule 3 — Blocking issue] Migration apply to dev DB deferred (no dev project)**

- **Found during:** Task 2 — plan's `<action>` ends with `psql "$SUPABASE_DEV_DB_URL" -f supabase/migrations/0008_rbac_role_default.sql`.
- **Issue:** Per STATE.md Open Externally-Blocked Items: "Dev Supabase project provisioning — `ivmf-checker-dev` not yet provisioned." `SUPABASE_DEV_DB_URL` is unset.
- **Fix:** Migration file landed at `supabase/migrations/0008_rbac_role_default.sql`. The Supabase CLI / `supabase db push` will apply 0001–0008 sequentially once the dev project exists, identical to the pattern documented for 00-02.
- **Files modified:** `supabase/migrations/0008_rbac_role_default.sql` (created)
- **Commit:** `6500f57`
- **How to retire:** Once `SUPABASE_DEV_DB_URL` is set, run `supabase db push` (or `psql -f` 0001 through 0008 in order). Then `cd worker && SUPABASE_DEV_DB_URL=... python3 -m pytest tests/test_rls_domain_allowlist.py tests/test_rbac.py tests/test_allowlist_admin.py -v` should pass all 7 tests.

**3. [Rule 2 — Missing critical functionality] `pnpm-workspace.yaml` scratch file added to `.gitignore`**

- **Found during:** Task 1 — `pnpm install` (pnpm 11) writes a `pnpm-workspace.yaml` containing only an `allowBuilds:` prompt placeholder.
- **Fix:** Added `pnpm-workspace.yaml` and `*.tsbuildinfo` (TS incremental cache) to `web/.gitignore`. Neither file is meaningful project content and committing them would create per-machine drift.
- **Files modified:** `web/.gitignore`
- **Commit:** `8b240f1`

### Authentication Gates

None encountered during this execution. The plan referenced live magic-link round-trip verification, but that depends on the dev Supabase project + Resend email — both externally blocked. Documented as Open Items below.

### Open Items (carry-forward to Wave 5 demo)

1. **Manual magic-link demo** — D-00-11 item 1 acceptance artifact. Once dev project + IT-provisioned email sender are live, run `cd web && pnpm dev`, visit `http://localhost:3000/me`, expect redirect to `/sign-in`, submit `jules@syr.edu`, receive magic link, click → land on `/me` showing email + role. Capture in `00-EVIDENCE.md` Item 1.
2. **`@gmail.com` 403 evidence** — submit `evil@gmail.com` after manual cookie injection (or sign-in with a non-allowlisted real address temporarily added to allowlist, then removed) and screenshot the 403 + "Sign-in restricted to allowed domains: syr.edu" response. Capture in `00-EVIDENCE.md` Item 1.
3. **Apply migration 0008** — once `SUPABASE_DEV_DB_URL` is set, apply via `supabase db push` and rerun the 7 worker integration tests.

## Known Stubs

None. Plan 00-03 documented `web/db/types.ts = Record<string, unknown>`; that stub is unchanged by this plan and not consumed by any code introduced here. No new placeholders or empty-data renders introduced.

## Requirements Closed

- **AUTH-01** — `signInWithOtp` magic-link form ships on `/sign-in`; allowlist-validated email; callback `exchangeCodeForSession` lands authed users on `/me`.
- **AUTH-02** — Admin extends allowlist by `UPDATE` on `app_config.email_domain_allowlist`; `test_allowlist_admin.py` proves the round-trip via `auth.is_allowed_domain()`.
- **AUTH-03** — `raw_app_meta_data.role` defaults to `'user'` on new `auth.users`; `auth.current_role_claim()` reads it from the JWT; `app_config_admin_all` policy uses the helper so middleware + RLS share the same source.

## Commits

- `8b240f1` — feat(00-04): Next.js 16 shell + Supabase SSR clients (AUTH-01 prep)
- `6500f57` — feat(00-04): middleware allowlist + magic-link sign-in + /me + RBAC migration
- `e9a1de8` — test(00-04): wire AUTH-01/02/03 vitest + pytest assertions

## Self-Check: PASSED

Files verified on disk:
- web/next.config.ts, tailwind.config.ts, postcss.config.mjs
- web/app/layout.tsx, app/globals.css, app/page.tsx
- web/app/(auth)/sign-in/page.tsx
- web/app/api/auth/callback/route.ts
- web/app/me/page.tsx
- web/middleware.ts
- web/lib/supabase/{server,client,service-role}.ts
- web/lib/auth/allowlist.ts
- web/.env.example
- web/pnpm-lock.yaml
- supabase/migrations/0008_rbac_role_default.sql
- web/tests/middleware-allowlist.test.ts (wired)
- web/tests/auth-magic-link.spec.ts (wired)
- worker/tests/test_rls_domain_allowlist.py (wired)
- worker/tests/test_rbac.py (wired)
- worker/tests/test_allowlist_admin.py (wired)

Commits verified in git log:
- 8b240f1 — Task 1
- 6500f57 — Task 2
- e9a1de8 — Task 3

Defense-in-depth verified by code inspection:
- `web/middleware.ts` reads allowlist via `getAllowlist(supabase)` (defense layer 1).
- `supabase/migrations/0006_app_config_seed.sql:auth.is_allowed_domain()` reads the same `app_config` row (defense layer 2).
- Both reference the canonical key `email_domain_allowlist` — no divergence.

Test runs verified:
- vitest: 8/8 passed.
- pytest: 7/7 collected, 7/7 skipped cleanly without dev DB; assertions ready for live run.
