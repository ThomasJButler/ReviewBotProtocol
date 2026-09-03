'use client'

import * as React from 'react'
import { TriangleAlert } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'

/** The last line of defence. Data problems are handled page by page with a
 * clear alert; this only fires on an unexpected render error. */
export default function ErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  React.useEffect(() => {
    console.error(error)
  }, [error])

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">
        Something went wrong
      </h1>
      <Alert variant="destructive">
        <TriangleAlert aria-hidden="true" />
        <AlertTitle>This page could not be rendered</AlertTitle>
        <AlertDescription>
          <p>{error.message || 'No message was given.'}</p>
          {error.digest ? (
            <p className="font-mono text-xs">Digest {error.digest}</p>
          ) : null}
          <p>
            If this keeps happening, check the terminal running{' '}
            <code className="font-mono">npm run dev</code> for the full trace.
          </p>
        </AlertDescription>
      </Alert>
      <Button type="button" onClick={reset}>
        Try again
      </Button>
    </div>
  )
}
