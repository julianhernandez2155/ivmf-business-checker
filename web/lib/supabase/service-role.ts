// Phase 00 Plan 04 (security: server-only key).
/**
 * Service-role client — SERVER ONLY. Never import from a Client Component.
 *
 * Security: SUPABASE_SERVICE_ROLE_KEY has NO `NEXT_PUBLIC_` prefix so it is not
 * inlined into the browser bundle. The runtime `typeof window` check is a
 * second defense — it throws loudly if someone accidentally imports this from
 * a 'use client' boundary.
 */
import { createClient } from '@supabase/supabase-js'

export function createServiceRoleClient() {
  if (typeof window !== 'undefined') {
    throw new Error('service-role client is server-only')
  }
  return createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!, // NO NEXT_PUBLIC_ prefix — server only
    { auth: { autoRefreshToken: false, persistSession: false } }
  )
}
