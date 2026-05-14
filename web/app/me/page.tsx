// Phase 00 Plan 04 — AUTH-01/03 authenticated landing page.
/**
 * /me — Server Component reading the validated user via getUser() and
 * surfacing email + role (sourced from app_metadata.role, defaulting to 'user').
 *
 * Per D-00-11 item 1: this page closes the magic-link round-trip demo.
 */
import { redirect } from 'next/navigation'
import { createServerClient } from '@/lib/supabase/server'

export default async function MePage() {
  const supabase = await createServerClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) {
    redirect('/sign-in')
  }

  const role =
    (user.app_metadata && typeof user.app_metadata.role === 'string'
      ? user.app_metadata.role
      : undefined) ?? 'user'

  return (
    <main className="mx-auto max-w-md p-8">
      <h1 className="text-2xl font-semibold mb-4">Welcome</h1>
      <dl className="space-y-2">
        <div className="flex gap-2">
          <dt className="font-medium">Email:</dt>
          <dd>{user.email}</dd>
        </div>
        <div className="flex gap-2">
          <dt className="font-medium">Role:</dt>
          <dd className="rounded bg-gray-100 px-2 py-0.5 text-sm">{role}</dd>
        </div>
        <div className="flex gap-2">
          <dt className="font-medium">User ID:</dt>
          <dd className="font-mono text-xs">{user.id}</dd>
        </div>
      </dl>
      <form action="/api/auth/sign-out" method="post" className="mt-6">
        <button type="submit" className="text-sm text-blue-600 underline">
          Sign out
        </button>
      </form>
    </main>
  )
}
