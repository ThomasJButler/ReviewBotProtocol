'use client'

import * as React from 'react'
import { ThumbsDown, ThumbsUp } from 'lucide-react'

import { recordFeedback } from '@/app/actions'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'

function toValue(useful: boolean | null): string {
  if (useful === true) return 'useful'
  if (useful === false) return 'not-useful'
  return ''
}

/**
 * Two toggles wired to a server action. The answer is written by the backend
 * on this machine; nothing leaves it.
 */
export function FeedbackButtons({
  reviewId,
  useful,
}: {
  reviewId: string
  useful: boolean | null
}) {
  const [value, setValue] = React.useState(toValue(useful))
  const [message, setMessage] = React.useState('')
  const [pending, startTransition] = React.useTransition()

  function onChange(next: string) {
    const previous = value
    setValue(next)
    setMessage('')
    startTransition(async () => {
      const answer =
        next === 'useful' ? true : next === 'not-useful' ? false : null
      const result = await recordFeedback(reviewId, answer)
      if (result.ok) {
        setMessage(
          answer === true
            ? 'Recorded as useful.'
            : answer === false
              ? 'Recorded as not useful.'
              : 'Answer cleared.'
        )
      } else {
        setValue(previous)
        setMessage(result.message ?? 'The answer could not be saved.')
      }
    })
  }

  return (
    <div className="flex flex-wrap items-center gap-3">
      <ToggleGroup
        type="single"
        variant="outline"
        value={value}
        onValueChange={onChange}
        disabled={pending}
        aria-label="Was this review useful?"
      >
        <ToggleGroupItem
          value="useful"
          className="data-[state=on]:border-ring data-[state=on]:font-semibold data-[state=on]:underline data-[state=on]:underline-offset-4"
        >
          <ThumbsUp aria-hidden="true" />
          Useful
        </ToggleGroupItem>
        <ToggleGroupItem
          value="not-useful"
          className="data-[state=on]:border-ring data-[state=on]:font-semibold data-[state=on]:underline data-[state=on]:underline-offset-4"
        >
          <ThumbsDown aria-hidden="true" />
          Not useful
        </ToggleGroupItem>
      </ToggleGroup>
      <p aria-live="polite" className="text-sm text-muted-foreground">
        {pending ? 'Saving…' : message}
      </p>
    </div>
  )
}
