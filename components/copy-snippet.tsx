'use client'

import * as React from 'react'
import { Check, Copy } from 'lucide-react'

import { Button } from '@/components/ui/button'

/** A command with a copy button. Falls back to a hint when the browser will
 * not give the page clipboard access. */
export function CopySnippet({ text, label }: { text: string; label?: string }) {
  const [state, setState] = React.useState<'idle' | 'copied' | 'failed'>('idle')

  async function copy() {
    try {
      await navigator.clipboard.writeText(text)
      setState('copied')
    } catch {
      setState('failed')
    }
    window.setTimeout(() => setState('idle'), 4000)
  }

  return (
    <div className="rounded-lg border border-border bg-muted/50">
      <div className="flex items-start gap-2 p-2">
        <pre className="min-w-0 flex-1 overflow-x-auto px-1 py-1 font-mono text-[0.8125rem] leading-6">
          <code>{text}</code>
        </pre>
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          onClick={copy}
          aria-label={label ? `Copy ${label}` : 'Copy to clipboard'}
        >
          {state === 'copied' ? (
            <Check aria-hidden="true" />
          ) : (
            <Copy aria-hidden="true" />
          )}
        </Button>
      </div>
      <p aria-live="polite" className="sr-only">
        {state === 'copied'
          ? 'Copied.'
          : state === 'failed'
            ? 'The browser blocked the copy. Select the text and copy it by hand.'
            : ''}
      </p>
      {state === 'failed' ? (
        <p className="px-3 pb-2 text-xs text-muted-foreground">
          The browser blocked the copy. Select the text and copy it by hand.
        </p>
      ) : null}
    </div>
  )
}
