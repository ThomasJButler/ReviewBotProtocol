'use client'

import * as React from 'react'

/** Replaces the root layout when the layout itself fails to render, which
 * `app/error.tsx` cannot catch because it renders inside that layout. It must
 * paint its own html and body, and it gets none of the app's providers or
 * styles beyond what is inline here. Next.js uses it in production builds
 * only; in development the overlay takes over. */
export default function GlobalError({
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
    <html lang="en-GB">
      <body
        style={{
          fontFamily: 'system-ui, sans-serif',
          margin: 0,
          padding: '2rem',
          color: '#111',
          background: '#fff',
        }}
      >
        <main>
          <h1 style={{ fontSize: '1.5rem', margin: '0 0 1rem' }}>
            ReviewBot Protocol could not render this page
          </h1>
          <p>{error.message || 'No message was given.'}</p>
          {error.digest ? (
            <p style={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>
              Digest {error.digest}
            </p>
          ) : null}
          <p>
            The terminal running the dashboard has the full trace. Reloading
            usually helps; if it does not, the backend at BACKEND_URL may be
            down or the token may be wrong.
          </p>
          <button
            type="button"
            onClick={reset}
            style={{ padding: '0.5rem 1rem', fontSize: '1rem' }}
          >
            Try again
          </button>
        </main>
      </body>
    </html>
  )
}
