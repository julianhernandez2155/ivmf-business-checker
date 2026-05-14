import { describe, it, expect } from 'vitest'

describe('magic-link login round-trip (AUTH-01)', () => {
  it.fails('redirects unauthenticated user from / to /sign-in', async () => {
    throw new Error('Wave 3: render middleware with no user; assert redirect to /sign-in')
  })

  it.fails('/me page shows email and role for authenticated user', async () => {
    throw new Error('Wave 3: mock authenticated session; render /me; assert email + role in DOM')
  })
})
