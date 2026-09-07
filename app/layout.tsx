import type { Metadata, Viewport } from 'next'

import './globals.css'
import { SiteHeader } from '@/components/site-header'
import { ThemeProvider } from '@/components/theme-provider'
import { TooltipProvider } from '@/components/ui/tooltip'

export const metadata: Metadata = {
  title: {
    default: 'ReviewBot Protocol',
    template: '%s | ReviewBot Protocol',
  },
  description:
    'Local dashboard for ReviewBot Protocol: what was reviewed, what the bot said, and whether it was any good.',
  icons: {
    icon: [
      { url: '/favicon.svg', type: 'image/svg+xml' },
      { url: '/favicon-32x32.png', sizes: '32x32', type: 'image/png' },
    ],
    apple: '/favicon-256x256.png',
  },
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en-GB" suppressHydrationWarning>
      <body className="min-h-screen bg-background text-foreground antialiased">
        <ThemeProvider>
          <TooltipProvider>
            <a
              href="#main"
              className="sr-only rounded-md bg-background px-3 py-2 text-sm font-medium underline focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:outline-2 focus:outline-offset-2 focus:outline-ring"
            >
              Skip to main content
            </a>
            <SiteHeader />
            <main
              id="main"
              tabIndex={-1}
              className="mx-auto w-full max-w-[1200px] px-4 py-10"
            >
              {children}
            </main>
          </TooltipProvider>
        </ThemeProvider>
      </body>
    </html>
  )
}
