import Link from 'next/link'
import { ThumbsDown, ThumbsUp } from 'lucide-react'

import { ReviewStatusBadge } from '@/components/severity-badge'
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { formatDuration, formatWhen, pullRequestUrl } from '@/lib/utils'
import type { Review, Severity } from '@/lib/api'

function Useful({ useful }: { useful: boolean | null }) {
  if (useful === null) {
    return <span className="text-muted-foreground">No answer</span>
  }
  const Icon = useful ? ThumbsUp : ThumbsDown
  return (
    <span className="inline-flex items-center gap-1.5">
      <Icon aria-hidden="true" className="size-3.5" />
      {useful ? 'Useful' : 'Not useful'}
    </span>
  )
}

const SEVERITIES: Severity[] = ['critical', 'high', 'medium', 'low', 'info']

function SeverityBreakdown({
  counts,
}: {
  counts: Partial<Record<Severity, number>> | undefined
}) {
  const parts = SEVERITIES.filter(s => (counts?.[s] ?? 0) > 0).map(
    s => `${counts?.[s]} ${s}`
  )
  if (parts.length === 0) return null
  return (
    <span className="block text-xs whitespace-nowrap text-muted-foreground">
      {parts.join(', ')}
    </span>
  )
}

export function ReviewsTable({
  reviews,
  total,
}: {
  reviews: Review[]
  total: number
}) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <Table>
        <TableCaption className="px-4 pb-3 text-left">
          {total === 1 ? '1 review' : `${total} reviews`}, newest first. Each
          row opens the full review.
        </TableCaption>
        <TableHeader>
          <TableRow>
            <TableHead scope="col">Repository</TableHead>
            <TableHead scope="col">Pull request</TableHead>
            <TableHead scope="col">When</TableHead>
            <TableHead scope="col">Model</TableHead>
            <TableHead scope="col">
              Files
              <span className="sr-only"> reviewed and skipped</span>
            </TableHead>
            <TableHead scope="col">Findings</TableHead>
            <TableHead scope="col">Duration</TableHead>
            <TableHead scope="col">Useful</TableHead>
            <TableHead scope="col">Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {reviews.map(review => (
            <TableRow key={review.id} className="relative">
              <TableCell className="font-medium">
                {/* The stretched link makes the whole row clickable while
                    keeping one tab stop per row. */}
                <Link
                  href={`/reviews/${review.id}`}
                  className="rounded-sm after:absolute after:inset-0 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
                >
                  {review.repository}
                </Link>
              </TableCell>
              <TableCell className="max-w-72">
                <a
                  href={pullRequestUrl(review.repository, review.pr_number)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="relative z-10 underline underline-offset-4"
                >
                  #{review.pr_number}
                </a>{' '}
                <span className="text-muted-foreground">
                  {review.pr_title ?? ''}
                </span>
              </TableCell>
              <TableCell className="whitespace-nowrap text-muted-foreground">
                <time dateTime={review.created_at ?? undefined} title="UTC">
                  {formatWhen(review.created_at)}
                </time>
              </TableCell>
              <TableCell className="font-mono text-xs">
                {review.model ?? 'none'}
              </TableCell>
              <TableCell className="whitespace-nowrap tabular-nums">
                {review.files_reviewed}
                <span className="text-muted-foreground">
                  {' '}
                  / {review.files_skipped}
                </span>
              </TableCell>
              <TableCell className="tabular-nums">
                {review.findings_count}
                <SeverityBreakdown counts={review.severity_counts} />
              </TableCell>
              <TableCell className="whitespace-nowrap tabular-nums">
                {formatDuration(review.duration_seconds)}
              </TableCell>
              <TableCell className="whitespace-nowrap">
                <Useful useful={review.useful} />
              </TableCell>
              <TableCell>
                <ReviewStatusBadge status={review.status} />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
