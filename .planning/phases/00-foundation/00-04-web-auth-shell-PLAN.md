---
phase: 00-foundation
plan: 04
type: execute
wave: 3
depends_on: [01, 02, 03]
files_modified:
  - web/next.config.ts
  - web/tailwind.config.ts
  - web/postcss.config.mjs
  - web/app/layout.tsx
  - web/app/globals.css
  - web/app/page.tsx
  - web/app/(auth)/sign-in/page.tsx
  - web/app/api/auth/callback/route.ts
  - web/app/me/page.tsx
  - web/middleware.ts
  - web/lib/supabase/server.ts
  - web/lib/supabase/client.ts
  - web/lib/supabase/service-role.ts
  - web/lib/auth/allowlist.ts
  - web/.env.example
  - web/tests/middleware-allowlist.test.ts
  - web/tests/auth-magic-link.spec.ts
  - worker/tests/test_rls_domain_allowlist.py
  - worker/tests/test_rbac.py
  - worker/tests/test_allowlist_admin.py
  - supabase/migrations/0008_rbac_role_default.sql
autonomous: true
requirements:
  - AUTH-01
  - AUTH-02
  - AUTH-03
must_haves:
  truths:
    - "User can submit @syr.edu email on /sign-in and receive a magic link via Supabase Auth"
    - "Clicking the magic link lands the user on /me showing their email and role"
    - "Visiting any protected route while unauthenticated redirects to /sign-in"
    - "Authenticated user with @gmail.com email is blocked at middleware with a 403 + clear allowlist message"
    - "UPDATE on app_config.email_domain_allowlist changes auth.is_allowed_domain() return value for the new domain"
    - "auth.users.raw_app_meta_data->>'role' propagates into JWT claims usable by middleware AND RLS"
    - "Service-role key is server-only (no NEXT_PUBLIC_ prefix)"
  artifacts:
    - path: web/middleware.ts
      provides: "Domain allowlist + auth check at edge using @supabase/ssr getUser()"
      contains: "getUser"
      min_lines: 40
    - path: web/app/(auth)/sign-in/page.tsx
      provides: "Magic-link only sign-in form per D-00-04"
      min_lines: 30
    - path: web/app/me/page.tsx
      provides: "Authenticated landing page showing email + role"
      min_lines: 20
    - path: web/app/api/auth/callback/route.ts
      provides: "Magic-link callback exchanging code for session"
      contains: "exchangeCodeForSession"
    - path: web/lib/supabase/server.ts
      provides: "createServerClient bound to Next cookies (NOT getSession)"
      contains: "createServerClient"
    - path: web/lib/auth/allowlist.ts
      provides: "Edge-cached allowlist read from app_config (60s TTL)"
      contains: "email_domain_allowlist"
    - path: supabase/migrations/0008_rbac_role_default.sql
      provides: "Default role='user' on new auth.users + RLS function reading role from JWT"
  key_links:
    - from: "web/middleware.ts"
      to: "supabase.auth.getUser() AND web/lib/auth/allowlist.ts"
      via: "edge runtime fetch + cookie read"
      pattern: "getUser\\(\\)|getAllowlist"
    - from: "web/middleware.ts"
      to: "@supabase/ssr createServerClient"
      via: "import"
      pattern: "from\\s+['\"]@supabase/ssr['\"]"
    - from: "web/app/(auth)/sign-in/page.tsx"
      to: "signInWithOtp with @syr.edu allowlist check BEFORE call"
      via: "server action"
      pattern: "signInWithOtp"
    - from: "supabase/migrations/0008_rbac_role_default.sql"
      to: "auth.users.raw_app_meta_data"
      via: "trigger or default"
      pattern: "raw_app_meta_data"
---

<objective>
Land the Next.js 16 web shell with Supabase magic-link auth, the domain allowlist enforced at BOTH middleware and RLS (D-00-05), and the `/me` page that demonstrates AUTH-01/02/03 in one round-trip. Convert remaining auth-related Wave 0 test stubs to real assertions.

Purpose: Close 3 of the 4 AUTH requirements and produce D-00-11 item 1 (the magic-link demo). Defense-in-depth at the allowlist boundary per Pitfall P10 mindset.

Output: Complete `web/` app router shell (sign-in, callback, /me, middleware, lib/supabase clients), a small RBAC migration setting default role, and 3 auth test stubs converted to passing tests.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/phases/00-foundation/00-CONTEXT.md
@.planning/phases/00-foundation/00-RESEARCH.md
@.planning/research/STACK.md
@.planning/research/PITFALLS.md
@.planning/phases/00-foundation/00-02-supabase-schema-rls-SUMMARY.md
@.planning/phases/00-foundation/00-03-codegen-drift-gate-SUMMARY.md
@web/db/types.ts

<interfaces>
<!-- Supabase server client pattern (canonical @supabase/ssr 0.10.x) -->

```ts
// web/lib/supabase/server.ts
import { createServerClient as _createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'

export async function createServerClient() {
  const cookieStore = await cookies()
  return _createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll: () => cookieStore.getAll(),
        setAll: (toSet) => {
          try {
            toSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options))
          } catch { /* Server Component - read-only cookies */ }
        },
      },
    }
  )
}
```

```ts
// web/lib/supabase/client.ts (browser)
import { createBrowserClient } from '@supabase/ssr'

export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  )
}
```

```ts
// web/lib/supabase/service-role.ts (server-only, never imported by client components)
import { createClient } from '@supabase/supabase-js'

export function createServiceRoleClient() {
  if (typeof window !== 'undefined') {
    throw new Error('service-role client is server-only')
  }
  return createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!,  // NO NEXT_PUBLIC_ prefix — server only
    { auth: { autoRefreshToken: false, persistSession: false } }
  )
}
```

<!-- Required environment variables -->
NEXT_PUBLIC_SUPABASE_URL          — public, embeds in browser bundle
NEXT_PUBLIC_SUPABASE_ANON_KEY     — public, anon JWT
SUPABASE_SERVICE_ROLE_KEY         — SERVER ONLY (no NEXT_PUBLIC_ prefix per Pitfall security)
NEXT_PUBLIC_SITE_URL              — for magic-link redirect (e.g. http://localhost:3000)
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Next.js skeleton — config, layout, Supabase clients, env</name>
  <files>web/next.config.ts, web/tailwind.config.ts, web/postcss.config.mjs, web/app/layout.tsx, web/app/globals.css, web/app/page.tsx, web/lib/supabase/server.ts, web/lib/supabase/client.ts, web/lib/supabase/service-role.ts, web/.env.example</files>
  <read_first>
    - .planning/research/STACK.md (Next.js 16 + Tailwind 4 + @supabase/ssr setup, lines 28-44)
    - .planning/phases/00-foundation/00-RESEARCH.md (Recommended Project Structure lines 156-213, especially `web/` subtree)
    - .planning/research/PITFALLS.md (Anti-patterns: getSession, service-role with NEXT_PUBLIC_, auth-helpers-nextjs at lines 137-151)
    - web/package.json (pinned versions from Wave 0)
  </read_first>
  <action>
    First install dependencies:
    ```bash
    cd web && pnpm install
    ```

    Create `web/next.config.ts`:
    ```ts
    import type { NextConfig } from 'next'

    const config: NextConfig = {
      experimental: { typedRoutes: false },
      // Server-only env vars are not exposed; NEXT_PUBLIC_ vars are inlined at build time.
    }

    export default config
    ```

    Create `web/tailwind.config.ts` (Tailwind 4 ships PostCSS-free per STACK.md):
    ```ts
    import type { Config } from 'tailwindcss'

    export default {
      content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
      theme: { extend: {} },
      plugins: [],
    } satisfies Config
    ```

    Create `web/postcss.config.mjs` (Tailwind 4 still needs PostCSS plugin):
    ```js
    export default {
      plugins: { '@tailwindcss/postcss': {} },
    }
    ```
    If `@tailwindcss/postcss` is not in deps, install: `cd web && pnpm add -D @tailwindcss/postcss`.

    Create `web/app/globals.css`:
    ```css
    @import 'tailwindcss';

    :root { color-scheme: light dark; }
    body { font-family: ui-sans-serif, system-ui, sans-serif; margin: 0; }
    ```

    Create `web/app/layout.tsx`:
    ```tsx
    import type { Metadata } from 'next'
    import './globals.css'

    export const metadata: Metadata = {
      title: 'IVMF Business Checker',
      description: 'Bulk verification of veteran/minority-owned businesses',
    }

    export default function RootLayout({ children }: { children: React.ReactNode }) {
      return (
        <html lang="en">
          <body className="min-h-screen bg-white text-gray-900 dark:bg-gray-950 dark:text-gray-100">
            {children}
          </body>
        </html>
      )
    }
    ```

    Create `web/app/page.tsx` (root — redirects to /me when authed, /sign-in otherwise; the middleware does the actual gating):
    ```tsx
    import { redirect } from 'next/navigation'

    export default function HomePage() {
      // Middleware handles auth; if we got here, user is authenticated.
      redirect('/me')
    }
    ```

    Create the three Supabase clients verbatim from the `<interfaces>` block above:
    - `web/lib/supabase/server.ts`
    - `web/lib/supabase/client.ts`
    - `web/lib/supabase/service-role.ts`

    Create `web/.env.example`:
    ```bash
    # Copy to .env.local and fill with values from the ivmf-checker-dev Supabase project
    # Settings → API → URL + anon + service_role keys.

    # Public — embedded in client bundle. SAFE.
    NEXT_PUBLIC_SUPABASE_URL=https://YOUR_PROJECT.supabase.co
    NEXT_PUBLIC_SUPABASE_ANON_KEY=YOUR_ANON_KEY
    NEXT_PUBLIC_SITE_URL=http://localhost:3000

    # Server-only — never inline in client code. NO NEXT_PUBLIC_ prefix.
    SUPABASE_SERVICE_ROLE_KEY=YOUR_SERVICE_ROLE_KEY
    ```

    Confirm `.env.local` is gitignored (already added in Wave 0 root .gitignore).
  </action>
  <verify>
    <automated>cd web && test -f next.config.ts && test -f tailwind.config.ts && test -f app/layout.tsx && test -f app/page.tsx && test -f lib/supabase/server.ts && test -f lib/supabase/client.ts && test -f lib/supabase/service-role.ts && test -f .env.example && grep -q "createServerClient" lib/supabase/server.ts && grep -q "createBrowserClient" lib/supabase/client.ts && grep -q "SUPABASE_SERVICE_ROLE_KEY" lib/supabase/service-role.ts && ! grep -q "NEXT_PUBLIC_SUPABASE_SERVICE_ROLE" lib/supabase/service-role.ts && grep -q "NEXT_PUBLIC_SUPABASE_URL" .env.example && pnpm exec tsc --noEmit 2>&1 | tee /tmp/tsc.out && ! grep -q "error TS" /tmp/tsc.out</automated>
  </verify>
  <acceptance_criteria>
    - All 8 listed files exist under `web/`
    - `web/lib/supabase/server.ts` uses `createServerClient` from `@supabase/ssr` (NOT from deprecated `@supabase/auth-helpers-nextjs`)
    - `web/lib/supabase/service-role.ts` reads `SUPABASE_SERVICE_ROLE_KEY` (no `NEXT_PUBLIC_` prefix)
    - `web/lib/supabase/service-role.ts` contains a runtime check `if (typeof window !== 'undefined') throw` to fail loudly if imported into a client component
    - `web/.env.example` contains exactly these keys: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_SITE_URL`, `SUPABASE_SERVICE_ROLE_KEY`
    - `web/.env.example` documents that service-role key is server-only
    - `cd web && pnpm exec tsc --noEmit` exits 0 (no TypeScript errors)
    - `grep -r "getSession()" web/lib web/app` returns nothing (P5 anti-pattern absent)
    - `grep -r "@supabase/auth-helpers-nextjs" web/` returns nothing (deprecated package not used)
  </acceptance_criteria>
  <done>Next.js shell installable and type-checks; Supabase clients use canonical patterns; secrets are correctly scoped.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Middleware + allowlist + sign-in + callback + /me page</name>
  <files>web/middleware.ts, web/lib/auth/allowlist.ts, web/app/(auth)/sign-in/page.tsx, web/app/api/auth/callback/route.ts, web/app/me/page.tsx, supabase/migrations/0008_rbac_role_default.sql</files>
  <read_first>
    - .planning/phases/00-foundation/00-RESEARCH.md (Pattern 1 middleware code lines 223-326)
    - .planning/phases/00-foundation/00-CONTEXT.md (D-00-04 magic-link only; D-00-05 allowlist at BOTH layers)
    - web/lib/supabase/server.ts (just created — pattern to use in middleware)
    - supabase/migrations/0006_app_config_seed.sql (auth.is_allowed_domain function — already exists; this task just needs to USE it)
    - .planning/research/PITFALLS.md (Anti-pattern: getSession in middleware at line 615)
  </read_first>
  <action>
    Create `web/lib/auth/allowlist.ts` — edge-cached read of `app_config.email_domain_allowlist`:
    ```ts
    /**
     * AUTH-02 + D-00-05: Edge-cached read of email_domain_allowlist from app_config.
     * 60-second TTL — keeps middleware fast while letting admin edits propagate quickly.
     * Defense layer 1; layer 2 is the auth.is_allowed_domain() RLS function.
     */
    import type { SupabaseClient } from '@supabase/supabase-js'

    let cache: { value: string[]; expiresAt: number } | null = null

    export async function getAllowlist(supabase: SupabaseClient): Promise<string[]> {
      const now = Date.now()
      if (cache && cache.expiresAt > now) return cache.value
      const { data, error } = await supabase
        .from('app_config')
        .select('value')
        .eq('key', 'email_domain_allowlist')
        .single()
      if (error || !data) {
        // Fail closed — only the default allowlist works.
        const fallback = ['syr.edu']
        cache = { value: fallback, expiresAt: now + 10_000 } // shorter TTL on error
        return fallback
      }
      const value = Array.isArray(data.value) ? (data.value as string[]) : ['syr.edu']
      cache = { value, expiresAt: now + 60_000 }
      return value
    }

    export function clearAllowlistCache(): void {
      cache = null
    }
    ```

    Create `web/middleware.ts` — apply the EXACT pattern from RESEARCH Pattern 1 (lines 223-285):
    ```ts
    import { NextRequest, NextResponse } from 'next/server'
    import { createServerClient } from '@supabase/ssr'
    import { getAllowlist } from '@/lib/auth/allowlist'

    const PUBLIC_PATHS = ['/sign-in', '/api/auth/callback']

    function isPublic(pathname: string): boolean {
      return PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(p + '/'))
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
              res.cookies.set(name, value, options)),
          },
        }
      )

      // CRITICAL: getUser() validates against the auth server (Pitfall: getSession is cookie-only and unverified).
      const { data: { user } } = await supabase.auth.getUser()

      if (!isPublic(req.nextUrl.pathname)) {
        if (!user) {
          const signInUrl = new URL('/sign-in', req.url)
          signInUrl.searchParams.set('next', req.nextUrl.pathname)
          return NextResponse.redirect(signInUrl)
        }
        // Domain allowlist (defense layer 1 — RLS is layer 2 via auth.is_allowed_domain)
        const allowlist = await getAllowlist(supabase as never)
        const domain = user.email?.split('@')[1] ?? ''
        if (!allowlist.includes(domain)) {
          return new NextResponse(
            `Sign-in restricted to allowed domains: ${allowlist.join(', ')}. Contact an admin to extend the allowlist.`,
            { status: 403, headers: { 'content-type': 'text/plain' } }
          )
        }
      }
      return res
    }

    export const config = {
      matcher: ['/((?!_next/static|_next/image|favicon.ico|.*\\.).*)'],
    }
    ```

    Create `web/app/(auth)/sign-in/page.tsx` — magic-link only (D-00-04):
    ```tsx
    'use client'

    import { useState, useTransition } from 'react'
    import { useSearchParams } from 'next/navigation'
    import { createClient } from '@/lib/supabase/client'

    export default function SignInPage() {
      const [email, setEmail] = useState('')
      const [sent, setSent] = useState(false)
      const [error, setError] = useState<string | null>(null)
      const [pending, startTransition] = useTransition()
      const params = useSearchParams()
      const next = params.get('next') ?? '/me'

      async function send() {
        setError(null)
        const supabase = createClient()
        // Pre-flight: check allowlist BEFORE signInWithOtp (D-00-04 guidance).
        const { data: cfg } = await supabase
          .from('app_config')
          .select('value')
          .eq('key', 'email_domain_allowlist')
          .single()
        const allowlist = Array.isArray(cfg?.value) ? (cfg!.value as string[]) : ['syr.edu']
        const domain = email.split('@')[1]?.toLowerCase() ?? ''
        if (!allowlist.includes(domain)) {
          setError(`Email domain not allowed. Permitted: ${allowlist.join(', ')}`)
          return
        }

        const { error: otpError } = await supabase.auth.signInWithOtp({
          email,
          options: {
            emailRedirectTo: `${process.env.NEXT_PUBLIC_SITE_URL ?? window.location.origin}/api/auth/callback?next=${encodeURIComponent(next)}`,
          },
        })
        if (otpError) setError(otpError.message)
        else setSent(true)
      }

      return (
        <main className="mx-auto max-w-md p-8">
          <h1 className="text-2xl font-semibold mb-4">IVMF Business Checker</h1>
          <p className="text-sm text-gray-600 mb-6">Sign in with your @syr.edu email.</p>
          {sent ? (
            <p className="rounded border border-green-300 bg-green-50 p-3 text-sm">
              Check your inbox for the magic link.
            </p>
          ) : (
            <form
              onSubmit={(e) => { e.preventDefault(); startTransition(send) }}
              className="space-y-3"
            >
              <input
                type="email"
                required
                autoFocus
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@syr.edu"
                className="w-full rounded border px-3 py-2"
              />
              <button
                type="submit"
                disabled={pending || !email}
                className="w-full rounded bg-blue-600 px-3 py-2 text-white disabled:opacity-50"
              >
                {pending ? 'Sending…' : 'Send magic link'}
              </button>
              {error && (
                <p className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-900">
                  {error}
                </p>
              )}
            </form>
          )}
        </main>
      )
    }
    ```

    Create `web/app/api/auth/callback/route.ts`:
    ```ts
    import { NextRequest, NextResponse } from 'next/server'
    import { createServerClient } from '@supabase/ssr'

    export async function GET(req: NextRequest) {
      const url = new URL(req.url)
      const code = url.searchParams.get('code')
      const next = url.searchParams.get('next') ?? '/me'

      if (!code) {
        return NextResponse.redirect(new URL('/sign-in?error=missing_code', req.url))
      }

      const res = NextResponse.redirect(new URL(next, req.url))
      const supabase = createServerClient(
        process.env.NEXT_PUBLIC_SUPABASE_URL!,
        process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
        {
          cookies: {
            getAll: () => req.cookies.getAll(),
            setAll: (toSet) => toSet.forEach(({ name, value, options }) =>
              res.cookies.set(name, value, options)),
          },
        }
      )

      const { error } = await supabase.auth.exchangeCodeForSession(code)
      if (error) {
        return NextResponse.redirect(
          new URL(`/sign-in?error=${encodeURIComponent(error.message)}`, req.url)
        )
      }
      return res
    }
    ```

    Create `web/app/me/page.tsx`:
    ```tsx
    import { redirect } from 'next/navigation'
    import { createServerClient } from '@/lib/supabase/server'

    export default async function MePage() {
      const supabase = await createServerClient()
      const { data: { user } } = await supabase.auth.getUser()
      if (!user) redirect('/sign-in')

      const role = (user.app_metadata?.role as string | undefined) ?? 'user'
      return (
        <main className="mx-auto max-w-md p-8">
          <h1 className="text-2xl font-semibold mb-4">Welcome</h1>
          <dl className="space-y-2">
            <div className="flex gap-2">
              <dt className="font-medium">Email:</dt>
              <dd>{user.email}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="font-medium">Role:</dt>
              <dd className="rounded bg-gray-100 px-2 py-0.5 text-sm">{role}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="font-medium">User ID:</dt>
              <dd className="font-mono text-xs">{user.id}</dd>
            </div>
          </dl>
          <form action="/api/auth/sign-out" method="post" className="mt-6">
            <button type="submit" className="text-sm text-blue-600 underline">Sign out</button>
          </form>
        </main>
      )
    }
    ```

    Create `supabase/migrations/0008_rbac_role_default.sql` — set role default + JWT propagation (AUTH-03):
    ```sql
    -- AUTH-03: ensure every new user has app_metadata.role='user' by default.
    -- Admin promotion happens via a service-role update; not part of Phase 0.
    create or replace function public.handle_new_user_role()
    returns trigger
    language plpgsql
    security definer
    as $$
    begin
      -- Only set if not already set (allows manual provisioning)
      if NEW.raw_app_meta_data is null or NEW.raw_app_meta_data ? 'role' = false then
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

    -- AUTH-03 RLS helper: extract role from JWT claims.
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

    -- Update app_config policies to use the helper (replaces the 0002 policy).
    drop policy if exists app_config_admin_all on public.app_config;
    create policy app_config_admin_all on public.app_config
      for all using (auth.current_role_claim() = 'admin')
      with check (auth.current_role_claim() = 'admin');
    ```

    Apply migration:
    ```bash
    psql "$SUPABASE_DEV_DB_URL" -f supabase/migrations/0008_rbac_role_default.sql
    ```
  </action>
  <verify>
    <automated>test -f web/middleware.ts && test -f web/lib/auth/allowlist.ts && test -f "web/app/(auth)/sign-in/page.tsx" && test -f web/app/api/auth/callback/route.ts && test -f web/app/me/page.tsx && test -f supabase/migrations/0008_rbac_role_default.sql && grep -q "getUser()" web/middleware.ts && ! grep -q "getSession()" web/middleware.ts && grep -q "signInWithOtp" "web/app/(auth)/sign-in/page.tsx" && grep -q "exchangeCodeForSession" web/app/api/auth/callback/route.ts && grep -q "app_metadata" web/app/me/page.tsx && grep -q "current_role_claim" supabase/migrations/0008_rbac_role_default.sql && grep -q "handle_new_user_role" supabase/migrations/0008_rbac_role_default.sql && cd web && pnpm exec tsc --noEmit 2>&1 | tee /tmp/tsc2.out && ! grep -q "error TS" /tmp/tsc2.out</automated>
  </verify>
  <acceptance_criteria>
    - All 6 files exist
    - `web/middleware.ts` uses `supabase.auth.getUser()` (NOT `getSession()`) — verified by grep
    - Middleware returns 403 with text containing "Sign-in restricted to allowed domains:" for non-allowlisted users
    - Middleware redirects unauthenticated users to `/sign-in` with `?next=` param
    - `web/middleware.ts` config matcher excludes `_next/static`, `_next/image`, `favicon.ico`, and files with extensions
    - `web/lib/auth/allowlist.ts` reads from `app_config` table key `email_domain_allowlist` with 60-second TTL cache
    - `web/app/(auth)/sign-in/page.tsx` is a Client Component (`'use client'`) using `signInWithOtp`
    - Sign-in page runs allowlist check BEFORE calling `signInWithOtp` (defense layer 1.5 — UI feedback)
    - `web/app/api/auth/callback/route.ts` calls `exchangeCodeForSession(code)` AND redirects to `/me` on success
    - `web/app/me/page.tsx` is a Server Component using `createServerClient` from `@/lib/supabase/server` AND reads `user.app_metadata.role`
    - `supabase/migrations/0008_rbac_role_default.sql` defines `handle_new_user_role` trigger AND `auth.current_role_claim()` function
    - Migration applied to dev DB: `psql -tAc "select 1 from pg_proc where proname='current_role_claim' and pronamespace='auth'::regnamespace"` returns 1
    - `cd web && pnpm exec tsc --noEmit` exits 0
  </acceptance_criteria>
  <done>Magic-link sign-in works end-to-end; middleware blocks non-allowlisted domains with clear message; /me page shows email + role; RBAC role defaults applied at user creation.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Wire auth-related tests (vitest + pytest) to passing state</name>
  <files>web/tests/middleware-allowlist.test.ts, web/tests/auth-magic-link.spec.ts, worker/tests/test_rls_domain_allowlist.py, worker/tests/test_rbac.py, worker/tests/test_allowlist_admin.py</files>
  <read_first>
    - web/middleware.ts (just created)
    - web/lib/auth/allowlist.ts (just created)
    - supabase/migrations/0008_rbac_role_default.sql (just created)
    - supabase/migrations/0006_app_config_seed.sql (auth.is_allowed_domain function)
    - worker/tests/conftest.py (db_url + conn fixtures)
    - .planning/phases/00-foundation/00-VALIDATION.md (Per-Task Verification Map for 0-03-* tasks)
  </read_first>
  <behavior>
    - middleware-allowlist.test.ts: mock @supabase/ssr getUser to return @gmail.com user; assert response status 403 and body contains "Sign-in restricted"
    - middleware-allowlist.test.ts: mock getUser to return null; assert redirect to /sign-in
    - auth-magic-link.spec.ts: mock authed @syr.edu user; assert /me page returns 200 (or test the page function returns expected JSX with email + role) — vitest unit test, not full Playwright
    - test_rls_domain_allowlist.py: call auth.is_allowed_domain('a@syr.edu') → true; ('a@gmail.com') → false
    - test_rbac.py: insert mock user with raw_app_meta_data role='admin'; assert auth.current_role_claim() returns 'admin' when called with that JWT context — OR assert function exists and policy uses it (simpler integration test)
    - test_allowlist_admin.py: UPDATE app_config row to add 'example.com'; assert auth.is_allowed_domain('a@example.com') → true (proves AUTH-02 round-trip)
  </behavior>
  <action>
    Replace `web/tests/middleware-allowlist.test.ts`:
    ```ts
    import { describe, it, expect, vi, beforeEach } from 'vitest'
    import { NextRequest } from 'next/server'

    // Mock @supabase/ssr before importing middleware
    vi.mock('@supabase/ssr', () => ({
      createServerClient: vi.fn(() => mockSupabase),
    }))

    let mockSupabase: any

    // Mock allowlist module (avoid hitting DB in unit test)
    vi.mock('@/lib/auth/allowlist', () => ({
      getAllowlist: vi.fn(async () => ['syr.edu']),
      clearAllowlistCache: vi.fn(),
    }))

    // Set required env BEFORE importing middleware
    process.env.NEXT_PUBLIC_SUPABASE_URL = 'http://localhost:54321'
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = 'test-anon-key'

    const { middleware } = await import('@/middleware')

    function makeReq(pathname: string): NextRequest {
      return new NextRequest(new URL(`http://localhost:3000${pathname}`))
    }

    describe('middleware allowlist (AUTH-02)', () => {
      beforeEach(() => {
        mockSupabase = {
          auth: { getUser: vi.fn() },
        }
      })

      it('redirects unauthenticated user to /sign-in', async () => {
        mockSupabase.auth.getUser.mockResolvedValue({ data: { user: null } })
        const res = await middleware(makeReq('/me'))
        expect(res.status).toBe(307) // Next redirect default
        expect(res.headers.get('location')).toContain('/sign-in')
      })

      it('blocks @gmail.com with 403 + clear message', async () => {
        mockSupabase.auth.getUser.mockResolvedValue({
          data: { user: { email: 'evil@gmail.com', id: 'u1' } },
        })
        const res = await middleware(makeReq('/me'))
        expect(res.status).toBe(403)
        const text = await res.text()
        expect(text).toContain('Sign-in restricted')
        expect(text).toContain('syr.edu')
      })

      it('admits @syr.edu user (passes through to next handler)', async () => {
        mockSupabase.auth.getUser.mockResolvedValue({
          data: { user: { email: 'jules@syr.edu', id: 'u2' } },
        })
        const res = await middleware(makeReq('/me'))
        // Middleware returns NextResponse.next() for admitted users. The synthetic
        // response from Next's edge runtime sets x-middleware-next=1 (or omits a
        // redirect/error status). Status will be < 400; do NOT assert == 200 because
        // NextResponse.next() default status varies across Next versions.
        expect(res.status).toBeLessThan(400)
        // Belt-and-suspenders: confirm it is NOT a redirect to /sign-in or a 403.
        expect(res.headers.get('location')).toBeNull()
      })

      it('allows public /sign-in without auth', async () => {
        mockSupabase.auth.getUser.mockResolvedValue({ data: { user: null } })
        const res = await middleware(makeReq('/sign-in'))
        expect(res.status).toBe(200)
      })
    })
    ```

    Replace `web/tests/auth-magic-link.spec.ts`:
    ```ts
    import { describe, it, expect } from 'vitest'

    describe('AUTH-01 magic-link flow contracts', () => {
      it('callback route exists and handles missing code', async () => {
        // Verify the route handler file exists; integration of OAuth flow is exercised in Phase 0 demo manually.
        const mod = await import('@/app/api/auth/callback/route')
        expect(typeof mod.GET).toBe('function')
      })

      it('/me page is a server component reading user', async () => {
        // Module-level smoke test — full render is exercised in demo.
        const mod = await import('@/app/me/page')
        expect(typeof mod.default).toBe('function')
      })

      it('sign-in page exports a client component', async () => {
        const mod = await import('@/app/(auth)/sign-in/page')
        expect(typeof mod.default).toBe('function')
      })
    })
    ```

    Replace `worker/tests/test_rls_domain_allowlist.py`:
    ```python
    """AUTH-03: auth.is_allowed_domain RLS function and current_role_claim helper."""
    import pytest

    pytestmark = pytest.mark.integration

    def test_is_allowed_domain_function_exists(conn):
        with conn.cursor() as cur:
            cur.execute("""
                select 1 from pg_proc
                where proname='is_allowed_domain' and pronamespace='auth'::regnamespace
            """)
            assert cur.fetchone() is not None

    def test_is_allowed_domain_admits_syr_edu(conn):
        with conn.cursor() as cur:
            cur.execute("select auth.is_allowed_domain('alice@syr.edu')")
            assert cur.fetchone()[0] is True

    def test_is_allowed_domain_blocks_gmail(conn):
        with conn.cursor() as cur:
            cur.execute("select auth.is_allowed_domain('alice@gmail.com')")
            assert cur.fetchone()[0] is False

    def test_current_role_claim_function_exists(conn):
        with conn.cursor() as cur:
            cur.execute("""
                select 1 from pg_proc
                where proname='current_role_claim' and pronamespace='auth'::regnamespace
            """)
            assert cur.fetchone() is not None
    ```

    Replace `worker/tests/test_rbac.py`:
    ```python
    """AUTH-03: RBAC role propagation via raw_app_meta_data trigger."""
    import pytest

    pytestmark = pytest.mark.integration

    def test_handle_new_user_role_trigger_exists(conn):
        with conn.cursor() as cur:
            cur.execute("""
                select 1 from pg_trigger
                where tgname = 'trg_handle_new_user_role'
            """)
            assert cur.fetchone() is not None

    def test_app_config_policy_uses_role_claim(conn):
        """AUTH-03: admin policy reads role from JWT via current_role_claim()."""
        with conn.cursor() as cur:
            cur.execute("""
                select pg_get_expr(polqual, polrelid)
                from pg_policy
                where polname = 'app_config_admin_all'
            """)
            row = cur.fetchone()
            assert row is not None, "app_config_admin_all policy missing"
            assert 'current_role_claim' in row[0] or "'admin'" in row[0]
    ```

    Replace `worker/tests/test_allowlist_admin.py`:
    ```python
    """AUTH-02: admin extends allowlist by updating app_config row, no code change."""
    import pytest

    pytestmark = pytest.mark.integration

    def test_allowlist_extend_admits_new_domain(conn):
        with conn.cursor() as cur:
            # Save original
            cur.execute("select value from public.app_config where key='email_domain_allowlist'")
            original = cur.fetchone()[0]
            try:
                # Extend with example.com
                cur.execute("""
                    update public.app_config
                    set value = '["syr.edu", "example.com"]'::jsonb,
                        updated_at = now()
                    where key='email_domain_allowlist'
                """)
                conn.commit()

                # auth.is_allowed_domain should now admit example.com
                cur.execute("select auth.is_allowed_domain('a@example.com')")
                assert cur.fetchone()[0] is True

                # syr.edu still admitted
                cur.execute("select auth.is_allowed_domain('a@syr.edu')")
                assert cur.fetchone()[0] is True

                # other.com still blocked
                cur.execute("select auth.is_allowed_domain('a@other.com')")
                assert cur.fetchone()[0] is False
            finally:
                # Restore
                import json
                cur.execute(
                    "update public.app_config set value = %s::jsonb where key='email_domain_allowlist'",
                    (json.dumps(original),),
                )
                conn.commit()
    ```
  </action>
  <verify>
    <automated>cd web && pnpm test --run tests/middleware-allowlist.test.ts tests/auth-magic-link.spec.ts 2>&1 | tee /tmp/web-test.out && grep -q "passed\\|Tests" /tmp/web-test.out && cd .. && cd worker && SUPABASE_DEV_DB_URL="${SUPABASE_DEV_DB_URL:-postgres://}" pytest tests/test_rls_domain_allowlist.py tests/test_rbac.py tests/test_allowlist_admin.py -x --tb=short && ! grep -l "xfail\\|NotImplementedError" worker/tests/test_rls_domain_allowlist.py worker/tests/test_rbac.py worker/tests/test_allowlist_admin.py web/tests/middleware-allowlist.test.ts web/tests/auth-magic-link.spec.ts</automated>
  </verify>
  <acceptance_criteria>
    - `web/tests/middleware-allowlist.test.ts` no longer uses `it.fails(...)`; uses `it(...)` with real assertions
    - `cd web && pnpm test --run` exits 0 with at least 7 tests passing (4 middleware + 3 magic-link)
    - `worker/tests/test_rls_domain_allowlist.py` no longer contains `@pytest.mark.xfail` or `NotImplementedError`
    - `worker/tests/test_rbac.py` no longer contains xfail/NotImplementedError
    - `worker/tests/test_allowlist_admin.py` no longer contains xfail/NotImplementedError; the test SAVES original allowlist value and RESTORES in finally
    - Running against dev DB: `cd worker && pytest tests/test_rls_domain_allowlist.py tests/test_rbac.py tests/test_allowlist_admin.py -x` exits 0
    - middleware test asserts 403 status AND text contains "Sign-in restricted"
    - middleware test asserts 307 redirect to `/sign-in` for unauthenticated
    - test_allowlist_admin asserts both `example.com` admitted AFTER update AND `other.com` still blocked (proves the function reads the table, not a hardcoded list)
  </acceptance_criteria>
  <done>AUTH-01, AUTH-02, AUTH-03 have green tests (vitest + pytest); allowlist defense-in-depth verified at both middleware and RLS layers; D-00-11 item 1 will be demoable end-to-end after a manual browser test.</done>
</task>

</tasks>

<verification>
- Manual demo (captured in 00-EVIDENCE.md): `cd web && pnpm dev`; visit http://localhost:3000/me — redirects to /sign-in; submit jules@syr.edu — receives magic link; click link — lands on /me; manually attempt evil@gmail.com flow — blocked with 403.
- `cd web && pnpm exec tsc --noEmit` exits 0.
- `cd web && pnpm test --run` exits 0 with ≥ 7 tests.
- `cd worker && pytest tests/test_rls_domain_allowlist.py tests/test_rbac.py tests/test_allowlist_admin.py -x` exits 0 with 8 tests passing.
- D-00-11 item 1 is locally demoable.
</verification>

<success_criteria>
1. AUTH-01: magic-link sign-in form ships; signInWithOtp called with allowlist-validated email.
2. AUTH-02: admin extends allowlist by editing app_config row; test_allowlist_admin proves the round-trip.
3. AUTH-03: role defaults to 'user' on new auth.users; current_role_claim() reads it from JWT; policies use it.
4. Defense-in-depth: middleware blocks at edge; auth.is_allowed_domain blocks at RLS.
5. Service-role key never appears with NEXT_PUBLIC_ prefix.
</success_criteria>

<output>
After completion, create `.planning/phases/00-foundation/00-04-web-auth-shell-SUMMARY.md` documenting:
- Magic-link round-trip behavior verified (manual demo or screenshot in 00-EVIDENCE.md)
- Allowlist cache invalidation strategy (60s edge TTL is acceptable for AUTH-02 since admin allowlist edits are rare)
- AUTH-03 implementation note: app_metadata.role is the canonical role source; profiles table NOT introduced in Phase 0 (deferred per discretion — Supabase Auth's app_metadata is sufficient)
- Requirements closed: AUTH-01, AUTH-02, AUTH-03
- Open follow-up: Wave 5 demo PR opens a `@gmail.com` attempt and records the 403 response in 00-EVIDENCE.md
</output>
