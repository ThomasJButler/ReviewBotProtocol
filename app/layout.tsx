import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import ErrorBoundary from '@/components/error-boundary'
import { ToastProvider } from '@/components/toast-provider'
import Navigation from '@/components/layout/Navigation'
import { AuthProvider } from '@/contexts/AuthContext'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'ReviewBot Protocol',
  description:
    'AI-powered code review protocol with automated PR analysis and security scanning',
  keywords: [
    'AI',
    'code review',
    'GitHub',
    'security',
    'development',
    'ReviewBot',
    'protocol',
  ],
  authors: [{ name: 'Tom Butler' }],
  openGraph: {
    title: 'ReviewBot Protocol',
    description:
      'AI-powered code review protocol with automated PR analysis and security scanning',
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
          <AuthProvider>
            <div className="min-h-screen bg-gradient-to-br from-deep-black via-gray-900 to-deep-black">
              <Navigation />
              <main>{children}</main>
            </div>
            <ToastProvider />
          </AuthProvider>
        </ErrorBoundary>
      </body>
    </html>
  )
}
