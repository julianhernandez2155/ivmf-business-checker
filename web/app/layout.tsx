// Phase 00 Plan 04: App Router root layout (AUTH-01 shell).
import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'IVMF Business Checker',
  description: 'Bulk verification of veteran/minority-owned businesses',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-white text-gray-900 dark:bg-gray-950 dark:text-gray-100">
        {children}
      </body>
    </html>
  )
}
