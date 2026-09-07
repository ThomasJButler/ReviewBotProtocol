import Link from 'next/link'
import { ThumbsDown, ThumbsUp } from 'lucide-react'

import { filesDone, visibleProgress } from '@/components/review-progress'
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

/** The owner muted, the name in full. */
function RepositoryName({ repository }: { repository: string }) {
  const slash = repository.indexOf('/')
  if (slash === -1) return <>{repository}</>
  return (
    <>
      <span className="opacity-70">{repository.slice(0, slash + 1)}</span>
      <span className="font-medium text-foreground/80">
        {repository.slice(slash + 1)}
      </span>
    </>
  )
}

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

/** How far a running review has got, in the words the badge leaves out. */
function RunningCount({ review }: { review: Review }) {
  const progress = visibleProgress(review.status, review.progress)
  if (!progress) return null
  return (
    <span className="ml-1.5 text-xs tabular-nums text-muted-foreground">
      {filesDone(progress)}/{progress.total}
      <span className="sr-only"> files done</span>
    </span>
  )
}

/** A review that has no numbers yet, so the columns say so instead of 0 / 0. */
function inProgress(review: Review): boolean {
  return review.status === 'running' || review.status === 'queued'
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
  showRepository = false,
}: {
  reviews: Review[]
  total: number
  /** With no repository filter on, each row names its repository under the title. */
  showRepository?: boolean
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
            <TableHead scope="col" className="min-w-[18rem]">
              Pull request
            </TableHead>
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
              {/* The shared cell never wraps. The title gets a bounded column, two
                  lines at most, and the whole of it on hover and on the review page.
                  The stretched link on the title makes the whole row open the
                  review while keeping one tab stop per row; the number is a
                  separate link to GitHub, raised above it. */}
              <TableCell className="max-w-[26rem] min-w-[18rem] whitespace-normal">
                <span
                  className="line-clamp-2 break-words"
                  title={review.pr_title ?? undefined}
                >
                  <a
                    href={pullRequestUrl(review.repository, review.pr_number)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="relative z-10 underline underline-offset-4"
                  >
                    #{review.pr_number}
                  </a>{' '}
                  <Link
                    href={`/reviews/${review.id}`}
                    className="rounded-sm text-muted-foreground after:absolute after:inset-0 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
                  >
                    {review.pr_title ?? (
                      <>
                        review
                        <span className="sr-only">
                          {' '}
                          of pull request {review.pr_number}
                        </span>
                      </>
                    )}
                  </Link>
                </span>
                {showRepository ? (
                  <span className="mt-0.5 block text-xs text-muted-foreground">
                    <RepositoryName repository={review.repository} />
                  </span>
                ) : null}
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
                {inProgress(review) ? (
                  <span className="text-muted-foreground">in progress</span>
                ) : (
                  <>
                    {review.files_reviewed}
                    <span className="text-muted-foreground">
                      {' '}
                      / {review.files_skipped}
                    </span>
                  </>
                )}
              </TableCell>
              <TableCell className="tabular-nums">
                {review.findings_count}
                <SeverityBreakdown counts={review.severity_counts} />
              </TableCell>
              <TableCell className="whitespace-nowrap tabular-nums">
                {inProgress(review) ? (
                  <span className="text-muted-foreground">in progress</span>
                ) : (
                  formatDuration(review.duration_seconds)
                )}
              </TableCell>
              <TableCell className="whitespace-nowrap">
                <Useful useful={review.useful} />
              </TableCell>
              <TableCell className="whitespace-nowrap pr-4">
                <ReviewStatusBadge status={review.status} />
                <RunningCount review={review} />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
