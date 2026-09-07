import Link from 'next/link'

export default function NotFound() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight">Not found</h1>
      <p className="text-muted-foreground">
        There is nothing at this address. The review may have been deleted, or
        the link may be from another machine.
      </p>
      <p>
        <Link
          href="/"
          className="rounded-sm underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
        >
          Back to reviews
        </Link>
      </p>
    </div>
  )
}
