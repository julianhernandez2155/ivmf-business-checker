// Phase 00 Plan 04 (AUTH-01).
/**
 * Supabase browser client.
 * Uses `@supabase/ssr` createBrowserClient — handles cookie storage in sync with
 * the server-side createServerClient pattern.
 */
import { createBrowserClient } from '@supabase/ssr'

export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  )
}
