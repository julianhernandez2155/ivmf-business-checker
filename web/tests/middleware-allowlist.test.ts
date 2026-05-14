// Phase 00 Plan 04 — AUTH-02 middleware allowlist tests (Wave 3 wire-up).
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { NextRequest } from 'next/server'

// --- Test doubles ---
// Mocks for @supabase/ssr must be hoisted BEFORE importing the middleware.

interface SupabaseUser { email: string; id: string }
interface MockSupabase {
  auth: { getUser: ReturnType<typeof vi.fn> }
}

let mockSupabase: MockSupabase

vi.mock('@supabase/ssr', () => ({
  createServerClient: vi.fn(() => mockSupabase),
}))

vi.mock('@/lib/auth/allowlist', () => ({
  getAllowlist: vi.fn(async () => ['syr.edu']),
  clearAllowlistCache: vi.fn(),
}))

// Required env vars must be set BEFORE the dynamic middleware import below.
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

  it('redirects unauthenticated user to /sign-in with ?next=', async () => {
    mockSupabase.auth.getUser.mockResolvedValue({ data: { user: null } })
    const res = await middleware(makeReq('/me'))
    expect(res.status).toBe(307)
    const location = res.headers.get('location')
    expect(location).toBeTruthy()
    expect(location).toContain('/sign-in')
    expect(location).toContain('next=%2Fme')
  })

  it('blocks @gmail.com with 403 + clear allowlist message', async () => {
    mockSupabase.auth.getUser.mockResolvedValue({
      data: { user: { email: 'evil@gmail.com', id: 'u1' } satisfies SupabaseUser },
    })
    const res = await middleware(makeReq('/me'))
    expect(res.status).toBe(403)
    const text = await res.text()
    expect(text).toContain('Sign-in restricted')
    expect(text).toContain('syr.edu')
  })

  it('admits @syr.edu user (passes through to next handler)', async () => {
    mockSupabase.auth.getUser.mockResolvedValue({
      data: { user: { email: 'jules@syr.edu', id: 'u2' } satisfies SupabaseUser },
    })
    const res = await middleware(makeReq('/me'))
    // NextResponse.next() default status varies across Next versions; assert
    // it is not an error AND not a redirect to /sign-in.
    expect(res.status).toBeLessThan(400)
    expect(res.headers.get('location')).toBeNull()
  })

  it('allows public /sign-in without auth (no redirect)', async () => {
    mockSupabase.auth.getUser.mockResolvedValue({ data: { user: null } })
    const res = await middleware(makeReq('/sign-in'))
    expect(res.status).toBeLessThan(400)
    expect(res.headers.get('location')).toBeNull()
  })

  it('allows public /api/auth/callback without auth', async () => {
    mockSupabase.auth.getUser.mockResolvedValue({ data: { user: null } })
    const res = await middleware(makeReq('/api/auth/callback?code=abc'))
    expect(res.status).toBeLessThan(400)
    expect(res.headers.get('location')).toBeNull()
  })
})
