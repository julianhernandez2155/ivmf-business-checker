// Phase 00 Plan 04 — AUTH-01 magic-link callback.
/**
 * Exchanges the magic-link `?code=` for a Supabase session, then redirects to
 * the original `next` path (or /me by default).
 *
 * Cookies set by `exchangeCodeForSession` are routed through the response
 * object so the browser receives them with the redirect.
 */
import { NextRequest, NextResponse } from 'next/server'
import { createServerClient } from '@supabase/ssr'

export async function GET(req: NextRequest): Promise<NextResponse> {
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
        setAll: (toSet) =>
          toSet.forEach(({ name, value, options }) =>
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
