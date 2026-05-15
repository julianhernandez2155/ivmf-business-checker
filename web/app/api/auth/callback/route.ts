// Phase 00 Plan 04 — AUTH-01 magic-link callback.
// GAP-4 fix (.planning/phases/00-foundation/00-VERIFICATION.md): the `next`
// query param is now sanitized via sanitizeNext() so absolute URLs cannot
// hijack the post-auth redirect. Whitelist: must start with '/' followed by
// a non-slash character (rejects '//evil', 'https://evil', 'javascript:', '').
/**
 * Exchanges the magic-link `?code=` for a Supabase session, then redirects to
 * the original (sanitized) `next` path or /me by default.
 *
 * Cookies set by `exchangeCodeForSession` are routed through the response
 * object so the browser receives them with the redirect.
 */
import { NextRequest, NextResponse } from 'next/server'
import { createServerClient } from '@supabase/ssr'

// GAP-4: '/foo' matches; '//evil', '/' alone, 'https://evil', 'javascript:' all rejected.
// Anchor + literal slash + one non-slash char rejects bare '/' (no second char)
// and protocol-relative '//host' in one pattern; the (?!\/) lookahead alternative
// would still admit bare '/' because end-of-string satisfies "not a slash".
const SAFE_NEXT_PATTERN = /^\/[^/]/

function sanitizeNext(raw: string | null): string {
  if (!raw) return '/me'
  // Reject anything that doesn't start with '/' followed by a non-slash char.
  // This rules out absolute URLs (http://, https://), protocol-relative (//host),
  // bare '/' (regex requires a second non-slash char), and schemes like
  // 'javascript:' or 'data:'.
  if (!SAFE_NEXT_PATTERN.test(raw)) return '/me'
  return raw
}

export async function GET(req: NextRequest): Promise<NextResponse> {
  const url = new URL(req.url)
  const code = url.searchParams.get('code')
  const next = sanitizeNext(url.searchParams.get('next'))

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
        setAll: (toSet) =>
          toSet.forEach(({ name, value, options }) =>
            res.cookies.set(name, value, options)),
      },
    },
  )

  const { error } = await supabase.auth.exchangeCodeForSession(code)
  if (error) {
    return NextResponse.redirect(
      new URL(`/sign-in?error=${encodeURIComponent(error.message)}`, req.url),
    )
  }
  return res
}

// Exported for unit-testing the sanitizer in isolation (GAP-4 regression test).
export { sanitizeNext, SAFE_NEXT_PATTERN }
