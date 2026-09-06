'use client'

import * as React from 'react'
import { useRouter } from 'next/navigation'

/**
 * Re-runs the server component on a timer, so a page watching a running job
 * keeps up with it. Nothing is drawn; the fetch happens on the server, so the
 * backend token stays there. The timer only fires while the tab is visible.
 */
export function AutoRefresh({ interval }: { interval: number }) {
  const router = useRouter()

  React.useEffect(() => {
    if (!(interval > 0)) return
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') router.refresh()
    }, interval)
    return () => window.clearInterval(timer)
  }, [interval, router])

  return null
}
