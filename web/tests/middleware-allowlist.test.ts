import { describe, it, expect } from 'vitest'

describe('middleware allowlist (AUTH-02)', () => {
  it.fails('blocks @gmail.com with 403 + clear message', async () => {
    // Wave 3 pending — middleware not yet implemented.
    throw new Error(
      'Wave 3: import middleware; mock @supabase/ssr getUser to return @gmail.com user; assert 403 + message contains allowlist'
    )
  })

  it.fails('admits @syr.edu user', async () => {
    throw new Error(
      'Wave 3: same as above with @syr.edu; assert NextResponse.next() called'
    )
  })
})
