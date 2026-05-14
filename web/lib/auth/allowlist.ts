// Phase 00 Plan 04 — AUTH-02 + D-00-05 edge-cached allowlist read.
/**
 * Edge-cached read of email_domain_allowlist from app_config.
 *
 * 60-second TTL — keeps middleware fast while letting admin edits propagate
 * quickly. This is defense layer 1 (middleware); layer 2 is the
 * auth.is_allowed_domain() RLS function (supabase/migrations/0006).
 *
 * On error (DB unreachable, row missing) the function FAILS CLOSED: it returns
 * only the default ['syr.edu'] allowlist and caches that with a shorter TTL so
 * recovery is fast once the DB is healthy again.
 */
import type { SupabaseClient } from '@supabase/supabase-js'

interface AllowlistCache {
  value: string[]
  expiresAt: number
}

let cache: AllowlistCache | null = null

const DEFAULT_ALLOWLIST: ReadonlyArray<string> = ['syr.edu']
const TTL_MS = 60_000
const ERROR_TTL_MS = 10_000

export async function getAllowlist(supabase: SupabaseClient): Promise<string[]> {
  const now = Date.now()
  if (cache && cache.expiresAt > now) return cache.value

  try {
    const { data, error } = await supabase
      .from('app_config')
      .select('value')
      .eq('key', 'email_domain_allowlist')
      .single()

    if (error || !data) {
      const fallback = [...DEFAULT_ALLOWLIST]
      cache = { value: fallback, expiresAt: now + ERROR_TTL_MS }
      return fallback
    }

    const value = Array.isArray(data.value)
      ? (data.value as string[])
      : [...DEFAULT_ALLOWLIST]
    cache = { value, expiresAt: now + TTL_MS }
    return value
  } catch {
    const fallback = [...DEFAULT_ALLOWLIST]
    cache = { value: fallback, expiresAt: now + ERROR_TTL_MS }
    return fallback
  }
}

/** Clear the allowlist cache. Exposed for tests; admin UI may also call. */
export function clearAllowlistCache(): void {
  cache = null
}
