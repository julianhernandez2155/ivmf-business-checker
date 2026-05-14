// Phase 00 Plan 04: root entry — middleware gates auth, this only fires when authed.
import { redirect } from 'next/navigation'

export default function HomePage() {
  // Middleware handles auth gating; if we got here, user is authenticated.
  redirect('/me')
}
