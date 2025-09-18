import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import ErrorBoundary from '@/components/error-boundary'
import { ToastProvider } from '@/components/toast-provider'
import Navigation from '@/components/layout/Navigation'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'AI Code Review Assistant',
  description: 'AI-powered code review system with GitHub integration',
  keywords: ['AI', 'code review', 'GitHub', 'security', 'development'],
  authors: [{ name: 'Tom Butler' }],
  openGraph: {
    title: 'AI Code Review Assistant',
    description: 'AI-powered code review system with GitHub integration',
    type: 'website',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="dark">
      <body className={inter.className}>
        <ErrorBoundary>
          <div className="min-h-screen bg-gradient-to-br from-deep-black via-gray-900 to-deep-black">
            <Navigation />
            <main>{children}</main>
          </div>
          <ToastProvider />
        </ErrorBoundary>
      </body>
    </html>
  )
}
