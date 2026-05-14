// Phase 00 Plan 04: Next.js 16 baseline config (AUTH-01 shell).
import type { NextConfig } from 'next'

const config: NextConfig = {
  experimental: { typedRoutes: false },
  // Server-only env vars are not exposed; NEXT_PUBLIC_ vars are inlined at build time.
}

export default config
