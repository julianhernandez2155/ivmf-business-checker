// Phase 00 Plan 04 — AUTH-01 magic-link sign-in (D-00-04: magic-link only).
'use client'

import { useState, useTransition } from 'react'
import { useSearchParams } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'

const DEFAULT_ALLOWLIST = ['syr.edu']

export default function SignInPage() {
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pending, startTransition] = useTransition()
  const params = useSearchParams()
  const next = params.get('next') ?? '/me'

  async function send(): Promise<void> {
    setError(null)
    const supabase = createClient()

    // Pre-flight allowlist check (defense layer 1.5 — UI feedback before signInWithOtp).
    // Real enforcement lives in middleware (layer 1) and Postgres RLS (layer 2).
    const { data: cfg } = await supabase
      .from('app_config')
      .select('value')
      .eq('key', 'email_domain_allowlist')
      .single()
    const allowlist: string[] = Array.isArray(cfg?.value)
      ? (cfg!.value as string[])
      : DEFAULT_ALLOWLIST
    const domain = email.split('@')[1]?.toLowerCase() ?? ''
    if (!allowlist.includes(domain)) {
      setError(`Email domain not allowed. Permitted: ${allowlist.join(', ')}`)
      return
    }

    const origin = process.env.NEXT_PUBLIC_SITE_URL ?? window.location.origin
    const { error: otpError } = await supabase.auth.signInWithOtp({
      email,
      options: {
        emailRedirectTo: `${origin}/api/auth/callback?next=${encodeURIComponent(next)}`,
      },
    })

    if (otpError) {
      setError(otpError.message)
      return
    }
    setSent(true)
  }

  return (
    <main className="mx-auto max-w-md p-8">
      <h1 className="text-2xl font-semibold mb-4">IVMF Business Checker</h1>
      <p className="text-sm text-gray-600 mb-6">Sign in with your @syr.edu email.</p>
      {sent ? (
        <p className="rounded border border-green-300 bg-green-50 p-3 text-sm">
          Check your inbox for the magic link.
        </p>
      ) : (
        <form
          onSubmit={(e) => { e.preventDefault(); startTransition(send) }}
          className="space-y-3"
        >
          <input
            type="email"
            required
            autoFocus
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@syr.edu"
            className="w-full rounded border px-3 py-2"
            aria-label="Email address"
          />
          <button
            type="submit"
            disabled={pending || !email}
            className="w-full rounded bg-blue-600 px-3 py-2 text-white disabled:opacity-50"
          >
            {pending ? 'Sending…' : 'Send magic link'}
          </button>
          {error && (
            <p
              role="alert"
              className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-900"
            >
              {error}
            </p>
          )}
        </form>
      )}
    </main>
  )
}
