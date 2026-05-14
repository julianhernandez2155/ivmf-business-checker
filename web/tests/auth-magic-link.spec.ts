// Phase 00 Plan 04 — AUTH-01 magic-link flow surface contracts (Wave 3 wire-up).
// Full browser round-trip is exercised in the D-00-11 manual demo (00-EVIDENCE.md);
// this file enforces that the module surface required by that demo exists.
import { describe, it, expect } from 'vitest'

// Env vars required when the modules construct Supabase clients on import.
process.env.NEXT_PUBLIC_SUPABASE_URL = 'http://localhost:54321'
process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = 'test-anon-key'

describe('AUTH-01 magic-link flow contracts', () => {
  it('callback route exports a GET handler', async () => {
    const mod = await import('@/app/api/auth/callback/route')
    expect(typeof mod.GET).toBe('function')
  })

  it('/me page exports a default Server Component function', async () => {
    const mod = await import('@/app/me/page')
    expect(typeof mod.default).toBe('function')
  })

  it('sign-in page exports a default Client Component function', async () => {
    const mod = await import('@/app/(auth)/sign-in/page')
    expect(typeof mod.default).toBe('function')
  })
})
