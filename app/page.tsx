import Link from 'next/link'
import { RefreshCw } from 'lucide-react'

import { refreshReviews } from '@/app/actions'
import { BackendAlert } from '@/components/backend-alert'
import { RepositoryFilter } from '@/components/repository-filter'
import { ReviewsTable } from '@/components/reviews-table'
import { StatusChip } from '@/components/status-chip'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { getStatus, listReviews } from '@/lib/api'

export const dynamic = 'force-dynamic'

export default async function ReviewsPage({
  searchParams,
}: {
  searchParams: Promise<{ repository?: string | string[] }>
}) {
  const params = await searchParams
  const repository = Array.isArray(params.repository)
    ? params.repository[0]
    : params.repository
  const [reviews, status] = await Promise.all([
    listReviews({ repository, limit: 50 }),
    getStatus(),
  ])

  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">Reviews</h1>
        <p className="text-muted-foreground">
          Every pull request this machine has reviewed, newest first.
        </p>
      </div>

      {!reviews.ok ? (
        <BackendAlert failure={reviews} />
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-4">
            <RepositoryFilter
              repositories={reviews.data.repositories}
              selected={repository}
            />
            <form action={refreshReviews}>
              <Button type="submit" variant="outline">
                <RefreshCw aria-hidden="true" />
                Refresh
              </Button>
            </form>
            <div className="ml-auto">
              <StatusChip initial={status} />
            </div>
          </div>

          {reviews.data.items.length === 0 ? (
            <Card>
              <CardHeader>
                <CardTitle>No reviews yet</CardTitle>
                <CardDescription>
                  {repository
                    ? `Nothing has been reviewed for ${repository}.`
                    : 'Nothing has been reviewed on this machine yet.'}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <p>Two things are worth checking:</p>
                <ul className="list-disc space-y-1 pl-5">
                  <li>
                    The GitHub App is installed on the repository you expect.
                  </li>
                  <li>
                    The App webhook points at this backend and pull request
                    events are switched on.
                  </li>
                </ul>
                <p>
                  <Link
                    href="/setup"
                    className="underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
                  >
                    Walk through setup
                  </Link>
                </p>
              </CardContent>
            </Card>
          ) : (
            <ReviewsTable
              reviews={reviews.data.items}
              total={reviews.data.total}
            />
          )}
        </>
      )}
    </div>
  )
}
