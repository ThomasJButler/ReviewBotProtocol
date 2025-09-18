import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { Toaster } from 'react-hot-toast'

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
        <div className="min-h-screen bg-gradient-to-br from-deep-black via-gray-900 to-deep-black">
          {children}
        </div>
        <Toaster
          position="top-right"
          toastOptions={{
            style: {
              background: 'rgba(26, 26, 26, 0.9)',
              color: '#ffffff',
              border: '1px solid rgba(0, 255, 0, 0.3)',
            },
          }}
        />
      </body>
    </html>
  )
}
