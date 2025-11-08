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
  icons: {
    icon: [
      { url: '/favicon-16x16.png', sizes: '16x16', type: 'image/png' },
      { url: '/favicon-32x32.png', sizes: '32x32', type: 'image/png' },
      { url: '/favicon-64x64.png', sizes: '64x64', type: 'image/png' },
    ],
    shortcut: '/favicon-32x32.png',
    apple: '/favicon-256x256.png',
    other: [
      {
        rel: 'icon',
        type: 'image/svg+xml',
        url: '/favicon.svg',
      },
    ],
  },
  openGraph: {
    title: 'ReviewBot Protocol',
    description:
      'AI-powered code review protocol with automated PR analysis and security scanning',
    type: 'website',
    images: [
      {
        url: '/og-image.png',
        width: 1200,
        height: 630,
        alt: 'ReviewBot Protocol - AI-Powered Code Review',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'ReviewBot Protocol',
    description:
      'AI-powered code review protocol with automated PR analysis and security scanning',
    images: ['/twitter-card.png'],
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
