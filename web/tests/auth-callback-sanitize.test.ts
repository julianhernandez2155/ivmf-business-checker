// GAP-4 regression (.planning/phases/00-foundation/00-VERIFICATION.md):
// The auth callback route must reject absolute `next` URLs so attacker-
// supplied links can't hijack the post-auth redirect off-origin.
//
// Tests sanitizeNext() directly (faster than full-route mocking with
// Supabase auth client) AND exercises SAFE_NEXT_PATTERN to confirm the
// regex shape. The full-route behavior is covered transitively because
// the route uses sanitizeNext(...) as the sole source of the redirect
// target.
import { describe, expect, it } from 'vitest'
import { sanitizeNext, SAFE_NEXT_PATTERN } from '@/app/api/auth/callback/route'

describe('sanitizeNext (GAP-4)', () => {
  it('falls back to /me when next is null', () => {
    expect(sanitizeNext(null)).toBe('/me')
  })

  it('falls back to /me when next is empty string', () => {
    expect(sanitizeNext('')).toBe('/me')
  })

  it('rejects absolute https URL (open-redirect attempt)', () => {
    expect(sanitizeNext('https://evil.example.com/path')).toBe('/me')
  })

  it('rejects absolute http URL', () => {
    expect(sanitizeNext('http://evil.example.com/')).toBe('/me')
  })

  it('rejects protocol-relative URL', () => {
    expect(sanitizeNext('//evil.example.com/path')).toBe('/me')
  })

  it('rejects javascript: scheme', () => {
    expect(sanitizeNext('javascript:alert(1)')).toBe('/me')
  })

  it('rejects data: scheme', () => {
    expect(sanitizeNext('data:text/html,evil')).toBe('/me')
  })

  it('rejects bare slash (no second segment)', () => {
    // The regex requires "/ followed by a non-slash CHAR", not just
    // "starts with /". Bare '/' has nothing after it and fails the
    // (?!\/) lookahead because there's nothing to NOT-be-a-slash.
    expect(sanitizeNext('/')).toBe('/me')
  })

  it('preserves /admin', () => {
    expect(sanitizeNext('/admin')).toBe('/admin')
  })

  it('preserves /runs/abc-123', () => {
    expect(sanitizeNext('/runs/abc-123')).toBe('/runs/abc-123')
  })

  it('preserves /me/profile', () => {
    expect(sanitizeNext('/me/profile')).toBe('/me/profile')
  })

  it('regex directly: matches /foo', () => {
    expect(SAFE_NEXT_PATTERN.test('/foo')).toBe(true)
  })

  it('regex directly: does not match //foo', () => {
    expect(SAFE_NEXT_PATTERN.test('//foo')).toBe(false)
  })

  it('regex directly: does not match https://x', () => {
    expect(SAFE_NEXT_PATTERN.test('https://x')).toBe(false)
  })
})
