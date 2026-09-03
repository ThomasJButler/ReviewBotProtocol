import Link from 'next/link'
import { notFound } from 'next/navigation'
import { ArrowLeft, ExternalLink } from 'lucide-react'

import { BackendAlert } from '@/components/backend-alert'
import { FeedbackButtons } from '@/components/feedback-buttons'
import { PostedBody } from '@/components/posted-body'
import { ReviewStatusBadge, SeverityBadge } from '@/components/severity-badge'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { getReview, type Finding, type Severity } from '@/lib/api'
import {
  formatDuration,
  formatWhen,
  pullRequestUrl,
  shortSha,
} from '@/lib/utils'

export const dynamic = 'force-dynamic'

const SEVERITY_ORDER: Severity[] = ['critical', 'high', 'medium', 'low', 'info']

function rank(severity: string): number {
  const index = SEVERITY_ORDER.indexOf(severity as Severity)
  return index === -1 ? SEVERITY_ORDER.length : index
}

function groupByFile(findings: Finding[]): [string, Finding[]][] {
  const groups = new Map<string, Finding[]>()
  for (const finding of findings) {
    const list = groups.get(finding.path)
    if (list) list.push(finding)
    else groups.set(finding.path, [finding])
  }
  for (const list of groups.values()) {
    list.sort((a, b) => rank(a.severity) - rank(b.severity) || a.line - b.line)
  }
  return [...groups.entries()].sort(
    (a, b) => rank(a[1][0].severity) - rank(b[1][0].severity)
  )
}

function Fact({
  label,
  children,
}: {
  label: string
  children: React.ReactNode
}) {
  return (
    <div className="space-y-0.5">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="text-sm">{children}</dd>
    </div>
  )
}

export default async function ReviewDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params
  const result = await getReview(id)

  if (!result.ok) {
    if (result.status === 404) notFound()
    return (
      <div className="space-y-8">
        <h1 className="text-2xl font-semibold tracking-tight">Review</h1>
        <BackendAlert failure={result} />
      </div>
    )
  }

  const review = result.data
  const grouped = groupByFile(review.findings)
  const counts = SEVERITY_ORDER.map(severity => ({
    severity,
    count: review.findings.filter(f => f.severity === severity).length,
  })).filter(entry => entry.count > 0)

  return (
    <div className="space-y-8">
      <Link
        href="/"
        className="inline-flex items-center gap-1.5 rounded-sm text-sm text-muted-foreground underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
      >
        <ArrowLeft aria-hidden="true" className="size-3.5" />
        All reviews
      </Link>

      <div className="space-y-3">
        <h1 className="text-2xl font-semibold tracking-tight">
          {review.repository} #{review.pr_number}
        </h1>
        <p className="text-muted-foreground">{review.pr_title ?? 'Untitled'}</p>
        <div className="flex flex-wrap items-center gap-2">
          <ReviewStatusBadge status={review.status} />
          {review.is_fork ? <Badge variant="outline">From a fork</Badge> : null}
          <a
            href={pullRequestUrl(review.repository, review.pr_number)}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 rounded-sm text-sm underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
          >
            Pull request on GitHub
            <ExternalLink aria-hidden="true" className="size-3.5" />
          </a>
          {review.comment_url ? (
            <a
              href={review.comment_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 rounded-sm text-sm underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
            >
              Posted review on GitHub
              <ExternalLink aria-hidden="true" className="size-3.5" />
            </a>
          ) : null}
        </div>
      </div>

      <dl className="grid grid-cols-2 gap-4 rounded-lg border border-border p-4 sm:grid-cols-3 lg:grid-cols-6">
        <Fact label="Head SHA">
          <span className="font-mono text-xs">{shortSha(review.head_sha)}</span>
        </Fact>
        <Fact label="Model">
          <span className="font-mono text-xs">{review.model ?? '—'}</span>
        </Fact>
        <Fact label="Started (UTC)">
          <time dateTime={review.created_at ?? undefined}>
            {formatWhen(review.created_at)}
          </time>
        </Fact>
        <Fact label="Duration">{formatDuration(review.duration_seconds)}</Fact>
        <Fact label="Tokens in">
          {review.prompt_tokens.toLocaleString('en-GB')}
        </Fact>
        <Fact label="Tokens out">
          {review.output_tokens.toLocaleString('en-GB')}
        </Fact>
      </dl>

      {review.status === 'failed' && review.error_message ? (
        <div className="rounded-lg border border-border bg-muted/50 p-4">
          <h2 className="text-sm font-semibold">The review failed</h2>
          <p className="mt-1 font-mono text-xs break-words text-muted-foreground">
            {review.error_message}
          </p>
        </div>
      ) : null}

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Was this useful?</h2>
        <p className="text-sm text-muted-foreground">
          The answer is written to the local database on this machine and is
          sent nowhere.
        </p>
        <FeedbackButtons reviewId={review.id} useful={review.useful} />
      </section>

      <Separator />

      <Tabs defaultValue="findings">
        <TabsList>
          <TabsTrigger value="findings">
            Findings ({review.findings.length})
          </TabsTrigger>
          <TabsTrigger value="posted">Posted review</TabsTrigger>
          <TabsTrigger value="skipped">
            Not reviewed ({review.skipped.length})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="findings" className="space-y-4 pt-4">
          {counts.length > 0 ? (
            <p className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
              {counts.map(entry => (
                <span
                  key={entry.severity}
                  className="inline-flex items-center gap-1.5"
                >
                  <SeverityBadge severity={entry.severity} />
                  {entry.count}
                </span>
              ))}
              {review.findings_dropped > 0
                ? `· ${review.findings_dropped} dropped as unusable`
                : null}
            </p>
          ) : null}

          {grouped.length === 0 ? (
            <Card>
              <CardHeader>
                <CardTitle>No findings</CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground">
                The model reported nothing on the {review.files_reviewed} file
                {review.files_reviewed === 1 ? '' : 's'} it read.
              </CardContent>
            </Card>
          ) : (
            grouped.map(([path, findings]) => (
              <section key={path} className="space-y-3">
                <h3 className="font-mono text-sm break-all">{path}</h3>
                <div className="space-y-3">
                  {findings.map(finding => (
                    <Card key={finding.id}>
                      <CardHeader>
                        <CardTitle className="flex flex-wrap items-center gap-2 text-sm">
                          <SeverityBadge severity={finding.severity} />
                          <Badge variant="secondary">{finding.category}</Badge>
                          <span className="text-muted-foreground">
                            Line {finding.line}
                          </span>
                        </CardTitle>
                        <p className="text-sm font-medium">{finding.title}</p>
                      </CardHeader>
                      <CardContent className="space-y-3 text-sm">
                        {finding.evidence ? (
                          <div>
                            <p className="text-xs text-muted-foreground">
                              Evidence
                            </p>
                            <pre className="mt-1 overflow-x-auto rounded-md border border-border bg-muted/50 p-2 font-mono text-xs">
                              <code>{finding.evidence}</code>
                            </pre>
                          </div>
                        ) : null}
                        {finding.recommendation ? (
                          <div>
                            <p className="text-xs text-muted-foreground">
                              Recommendation
                            </p>
                            <p className="mt-1">{finding.recommendation}</p>
                          </div>
                        ) : null}
                        {finding.confidence !== null ? (
                          <p className="text-xs text-muted-foreground">
                            Model confidence{' '}
                            {Math.round(finding.confidence * 100)} per cent
                          </p>
                        ) : null}
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </section>
            ))
          )}
        </TabsContent>

        <TabsContent value="posted" className="pt-4">
          {review.summary ? (
            <div className="rounded-lg border border-border p-4">
              <PostedBody body={review.summary} />
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              Nothing was posted for this review.
            </p>
          )}
        </TabsContent>

        <TabsContent value="skipped" className="pt-4">
          {review.skipped.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Every file in the pull request was read.
            </p>
          ) : (
            <ul className="space-y-2 text-sm">
              {review.skipped.map(file => (
                <li key={file.path} className="flex flex-wrap gap-2">
                  <span className="font-mono text-xs break-all">
                    {file.path}
                  </span>
                  <span className="text-muted-foreground">{file.reason}</span>
                </li>
              ))}
            </ul>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}
