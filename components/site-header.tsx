'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'

import { ThemeToggle } from '@/components/theme-toggle'
import { cn } from '@/lib/utils'

const NAV = [
  { href: '/', label: 'Reviews' },
  { href: '/status', label: 'Status' },
  { href: '/setup', label: 'Setup' },
]

export function SiteHeader() {
  const pathname = usePathname()

  return (
    <header className="border-b border-border">
      <div className="mx-auto flex h-14 w-full max-w-[1100px] items-center gap-6 px-4">
        <Link
          href="/"
          className="rounded-sm text-sm font-semibold tracking-tight focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring"
        >
          ReviewBot Protocol
        </Link>
        <nav aria-label="Main" className="flex items-center gap-1">
          {NAV.map(item => {
            const active =
              item.href === '/'
                ? pathname === '/' || pathname.startsWith('/reviews')
                : pathname.startsWith(item.href)
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? 'page' : undefined}
                className={cn(
                  'rounded-md px-2 py-1 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring',
                  active
                    ? 'font-medium text-foreground underline underline-offset-8'
                    : 'text-muted-foreground hover:text-foreground'
                )}
              >
                {item.label}
              </Link>
            )
          })}
        </nav>
        <div className="ml-auto">
          <ThemeToggle />
        </div>
      </div>
    </header>
  )
}
