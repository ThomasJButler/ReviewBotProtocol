'use client'

import * as React from 'react'

import { readStatus } from '@/app/actions'
import { cn } from '@/lib/utils'
import type { ApiResult, Status } from '@/lib/api'

function describe(state: ApiResult<Status>): {
  text: string
  tone: 'ok' | 'warn' | 'bad'
} {
  if (!state.ok) return { text: 'Backend unreachable', tone: 'bad' }
  const { queue, ollama } = state.data
  if (!queue.alive) return { text: 'Review worker stopped', tone: 'bad' }
  const queueText =
    queue.depth === 1 ? '1 job queued' : `${queue.depth} jobs queued`
  if (!ollama.reachable) {
    return { text: `Ollama unreachable, ${queueText}`, tone: 'bad' }
  }
  if (!ollama.model_present) {
    return {
      text: `Model ${ollama.model} not pulled, ${queueText}`,
      tone: 'warn',
    }
  }
  return { text: `Ollama ready, ${queueText}`, tone: 'ok' }
}

const TONES = {
  ok: 'border-emerald-700/50 text-emerald-800 dark:border-emerald-400/40 dark:text-emerald-300',
  warn: 'border-amber-700/50 text-amber-800 dark:border-amber-400/40 dark:text-amber-300',
  bad: 'border-red-700/50 text-red-800 dark:border-red-400/40 dark:text-red-300',
}

const DOTS = {
  ok: 'bg-emerald-600 dark:bg-emerald-400',
  warn: 'bg-amber-600 dark:bg-amber-400',
  bad: 'bg-red-600 dark:bg-red-400',
}

/**
 * Queue depth and Ollama reachability, refreshed every 30 seconds while the
 * tab is visible. The refresh is a server action, so the backend token stays
 * on the server.
 */
export function StatusChip({ initial }: { initial: ApiResult<Status> }) {
  const [state, setState] = React.useState(initial)

  React.useEffect(() => {
    let cancelled = false

    async function poll() {
      if (document.visibilityState !== 'visible') return
      const next = await readStatus()
      if (!cancelled) setState(next)
    }

    const timer = window.setInterval(poll, 30_000)
    document.addEventListener('visibilitychange', poll)
    return () => {
      cancelled = true
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', poll)
    }
  }, [])

  const { text, tone } = describe(state)

  return (
    <p
      role="status"
      aria-live="polite"
      className={cn(
        'inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs',
        TONES[tone]
      )}
    >
      <span
        aria-hidden="true"
        className={cn('size-1.5 shrink-0 rounded-full', DOTS[tone])}
      />
      {text}
    </p>
  )
}
