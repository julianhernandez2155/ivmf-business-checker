// Phase 00 Plan 04 (AUTH-01/03).
/**
 * Supabase server client bound to Next.js cookies.
 *
 * Uses `@supabase/ssr` (NOT the deprecated `@supabase/auth-helpers-nextjs`).
 * Server Components MUST call `supabase.auth.getUser()` — never `getSession()` —
 * because `getUser()` validates against the auth server while `getSession()`
 * only reads the (potentially tampered) cookie. See PITFALLS P5.
 */
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
          } catch {
            // Server Component invocation — cookies() is read-only.
            // The middleware or a Route Handler will refresh on the next request.
          }
        },
      },
    }
  )
}
