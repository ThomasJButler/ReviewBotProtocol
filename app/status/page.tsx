import Link from 'next/link'
import { RefreshCw } from 'lucide-react'

import { refreshStatus } from '@/app/actions'
import { AutoRefresh } from '@/components/auto-refresh'
import { BackendAlert } from '@/components/backend-alert'
import { CopySnippet } from '@/components/copy-snippet'
import { ReviewProgressBar } from '@/components/review-progress'
import { ReviewStatusBadge } from '@/components/severity-badge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { getStatus, listDeliveries } from '@/lib/api'
import { formatBytes, formatWhen, shortSha } from '@/lib/utils'

export const dynamic = 'force-dynamic'

export const metadata = { title: 'Status' }

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="text-right text-sm">{value}</dd>
    </div>
  )
}

function YesNo({
  value,
  yes,
  no,
}: {
  value: boolean
  yes: string
  no: string
}) {
  return (
    <Badge
      variant="outline"
      className={
        value
          ? 'border-emerald-700/50 text-emerald-800 dark:border-emerald-400/40 dark:text-emerald-300'
          : 'border-red-700/50 text-red-800 dark:border-red-400/40 dark:text-red-300'
      }
    >
      {value ? yes : no}
    </Badge>
  )
}

export default async function StatusPage() {
  const [status, deliveries] = await Promise.all([
    getStatus(),
    listDeliveries(20),
  ])

  const current = status.ok ? status.data.queue.current : null

  return (
    <div className="space-y-8">
      {/* A job in flight moves file by file, so watch it closely while there
          is one and leave the backend alone the rest of the time. */}
      <AutoRefresh interval={current ? 2000 : 10_000} />

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-2">
          <h1 className="text-2xl font-semibold tracking-tight">Status</h1>
          <p className="text-muted-foreground">
            What the backend on this machine can see right now.
          </p>
        </div>
        <form action={refreshStatus}>
          <Button type="submit" variant="outline">
            <RefreshCw aria-hidden="true" />
            Refresh
          </Button>
        </form>
      </div>

      {!status.ok ? (
        <BackendAlert failure={status} />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Ollama</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="divide-y divide-border">
                <Row
                  label="Reachable"
                  value={
                    <YesNo
                      value={status.data.ollama.reachable}
                      yes="Reachable"
                      no="Not reachable"
                    />
                  }
                />
                <Row
                  label="Model configured"
                  value={
                    <span className="font-mono text-xs">
                      {status.data.ollama.model}
                    </span>
                  }
                />
                <Row
                  label="Model pulled"
                  value={
                    <YesNo
                      value={status.data.ollama.model_present}
                      yes="Present"
                      no="Not pulled"
                    />
                  }
                />
                <Row
                  label="Model address"
                  value={status.data.ollama.base_url ?? 'not reported'}
                />
                <Row
                  label="Cross-examiner"
                  value={
                    status.data.cross_model ? (
                      <span className="font-mono text-xs">
                        {status.data.cross_model}
                        {status.data.ollama.cross_model_present === false
                          ? ' (not pulled)'
                          : ''}
                      </span>
                    ) : (
                      'off'
                    )
                  }
                />
                {status.data.ollama.error ? (
                  <Row
                    label="Last error"
                    value={
                      <span className="font-mono text-xs">
                        {status.data.ollama.error}
                      </span>
                    }
                  />
                ) : null}
                <Row
                  label="Loaded models"
                  value={
                    status.data.ollama.loaded.length === 0 ? (
                      'None loaded'
                    ) : (
                      <ul className="space-y-1">
                        {status.data.ollama.loaded.map(model => (
                          <li key={model.name ?? 'unknown'}>
                            <span className="font-mono text-xs">
                              {model.name ?? 'unknown'}
                            </span>
                            <span className="text-muted-foreground">
                              {model.context_length
                                ? ` · ${model.context_length.toLocaleString('en-GB')} context`
                                : ''}
                              {model.size_vram
                                ? ` · ${formatBytes(model.size_vram)} VRAM`
                                : ''}
                            </span>
                          </li>
                        ))}
                      </ul>
                    )
                  }
                />
              </dl>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Queue</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="divide-y divide-border">
                <Row
                  label="Worker"
                  value={
                    <YesNo
                      value={status.data.queue.alive}
                      yes="Running"
                      no="Stopped"
                    />
                  }
                />
                <Row label="Depth" value={status.data.queue.depth} />
                {status.data.queue.abandoned > 0 ? (
                  <Row
                    label="Stuck workers"
                    value={status.data.queue.abandoned}
                  />
                ) : null}
                <Row
                  label="Current job"
                  value={
                    current ? (
                      <div className="space-y-1.5">
                        <span>
                          {current.repository} #{current.pr_number} at{' '}
                          <span className="font-mono text-xs">
                            {shortSha(current.head_sha)}
                          </span>
                        </span>
                        <ReviewProgressBar progress={current.progress} />
                      </div>
                    ) : (
                      'Idle'
                    )
                  }
                />
                <Row label="Backend version" value={status.data.version} />
              </dl>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Database</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="divide-y divide-border">
                <Row
                  label="Reachable"
                  value={
                    <YesNo
                      value={status.data.database}
                      yes="Healthy"
                      no="Not answering"
                    />
                  }
                />
              </dl>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Limits</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="divide-y divide-border">
                <Row
                  label="Files per review"
                  value={status.data.limits.max_files_per_review}
                />
                <Row
                  label="Patch size"
                  value={formatBytes(status.data.limits.max_patch_bytes)}
                />
                <Row
                  label="Review timeout"
                  value={`${status.data.limits.review_timeout_seconds} s`}
                />
                <Row
                  label="Budget per file"
                  value={
                    status.data.limits.review_seconds_per_file > 0
                      ? `${status.data.limits.review_seconds_per_file} s`
                      : 'off'
                  }
                />
                <Row
                  label="Context window"
                  value={status.data.limits.num_ctx.toLocaleString('en-GB')}
                />
              </dl>
            </CardContent>
          </Card>
        </div>
      )}

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Recent deliveries</h2>
        {!deliveries.ok ? (
          <BackendAlert failure={deliveries} />
        ) : deliveries.data.items.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No webhook deliveries have arrived yet. Send a ping from the App
            settings page to check the route.
          </p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-border">
            <Table>
              <TableCaption className="px-4 pb-3 text-left">
                The last {deliveries.data.items.length} webhook deliveries this
                backend accepted.
              </TableCaption>
              <TableHeader>
                <TableRow>
                  <TableHead scope="col">Received (UTC)</TableHead>
                  <TableHead scope="col">Event</TableHead>
                  <TableHead scope="col">Repository</TableHead>
                  <TableHead scope="col">Pull request</TableHead>
                  <TableHead scope="col">Status</TableHead>
                  <TableHead scope="col">Review</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {deliveries.data.items.map(delivery => (
                  <TableRow key={delivery.delivery_id}>
                    <TableCell className="whitespace-nowrap text-muted-foreground">
                      <time dateTime={delivery.received_at ?? undefined}>
                        {formatWhen(delivery.received_at)}
                      </time>
                    </TableCell>
                    <TableCell>
                      {delivery.event}
                      {delivery.action ? `.${delivery.action}` : ''}
                    </TableCell>
                    <TableCell>{delivery.repository ?? 'none'}</TableCell>
                    <TableCell className="tabular-nums">
                      {delivery.pr_number ? `#${delivery.pr_number}` : 'none'}
                    </TableCell>
                    <TableCell>
                      <ReviewStatusBadge status={delivery.status} />
                    </TableCell>
                    <TableCell>
                      {delivery.review_id ? (
                        <Link
                          href={`/reviews/${delivery.review_id}`}
                          className="rounded-sm underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
                        >
                          Open
                        </Link>
                      ) : (
                        'none'
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Egress proof</h2>
        <p className="max-w-prose text-sm text-muted-foreground">
          In local mode a review reads the diff from GitHub, thinks on this
          machine and writes the comment back; nothing else leaves it. Hosted
          mode runs the same bot on a server you rent, described in
          docs/HOSTED_MODEL_PLAN.md. Two commands prove the local claim: the
          first runs whole reviews (GitHub answered in-process, a fake model)
          inside a socket-level guard that allows loopback only, the second runs
          a real review with a real model inside a container with no network at
          all.
        </p>
        <CopySnippet
          text="cd backend && .venv/bin/python -m pytest tests/test_no_egress.py"
          label="the socket guard test command"
        />
        <CopySnippet
          text="./scripts/prove-local.sh"
          label="the no-network container command"
        />
        <p className="text-sm text-muted-foreground">
          The backend does not record the result of either run, so read it from
          the terminal where you ran it.
        </p>
      </section>
    </div>
  )
}
