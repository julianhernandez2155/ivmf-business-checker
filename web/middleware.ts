// Phase 00 Plan 04 — AUTH-01..03 edge gating.
/**
 * Next.js middleware: defense layer 1 of the domain allowlist (D-00-05).
 *
 * - Calls `supabase.auth.getUser()` (NOT `getSession()`); getUser validates
 *   against the auth server so a tampered cookie does not bypass auth.
 * - Reads `app_config.email_domain_allowlist` via the edge-cached helper.
 * - Returns 403 with a clear message for non-allowlisted authenticated users.
 * - Redirects unauthenticated requests to /sign-in (preserves `?next=`).
 *
 * Layer 2 is the Postgres RLS function `auth.is_allowed_domain()` defined in
 * supabase/migrations/0006_app_config_seed.sql — reading only one of the two
 * layers is a known-bypass shape per CONTEXT.md D-00-05.
 */
import { NextRequest, NextResponse } from 'next/server'
import { createServerClient } from '@supabase/ssr'
import { getAllowlist } from '@/lib/auth/allowlist'

const PUBLIC_PATHS = ['/sign-in', '/api/auth/callback']

function isPublic(pathname: string): boolean {
  return PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(p + '/'))
}

export async function middleware(req: NextRequest): Promise<NextResponse> {
  const res = NextResponse.next()

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll: () => req.cookies.getAll(),
        setAll: (toSet) =>
          toSet.forEach(({ name, value, options }) =>
            res.cookies.set(name, value, options)),
      },
    }
  )

  // CRITICAL: getUser() validates against the auth server.
  // getSession() reads cookies only and is UNVERIFIED — never use it in middleware.
  const { data: { user } } = await supabase.auth.getUser()

  if (isPublic(req.nextUrl.pathname)) {
    return res
  }

  if (!user) {
    const signInUrl = new URL('/sign-in', req.url)
    signInUrl.searchParams.set('next', req.nextUrl.pathname)
    return NextResponse.redirect(signInUrl)
  }

  // Domain allowlist — defense layer 1. Layer 2 is auth.is_allowed_domain() in RLS.
  const allowlist = await getAllowlist(supabase as never)
  const domain = (user.email?.split('@')[1] ?? '').toLowerCase()
  if (!allowlist.includes(domain)) {
    return new NextResponse(
      `Sign-in restricted to allowed domains: ${allowlist.join(', ')}. Contact an admin to extend the allowlist.`,
      { status: 403, headers: { 'content-type': 'text/plain' } }
    )
  }

  return res
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico|.*\\.).*)'],
}
