import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import type { Severity } from '@/lib/api'

/* Colour is never the only signal: every badge spells out the word. */
const SEVERITY_STYLES: Record<Severity, string> = {
  critical:
    'border-red-700/50 bg-red-700/10 text-red-800 dark:border-red-400/40 dark:text-red-300',
  high: 'border-orange-700/50 bg-orange-700/10 text-orange-800 dark:border-orange-400/40 dark:text-orange-300',
  medium:
    'border-amber-700/50 bg-amber-700/10 text-amber-800 dark:border-amber-400/40 dark:text-amber-300',
  low: 'border-sky-700/50 bg-sky-700/10 text-sky-800 dark:border-sky-400/40 dark:text-sky-300',
  info: 'border-border bg-muted text-muted-foreground',
}

const SEVERITY_LABELS: Record<Severity, string> = {
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
  info: 'Info',
}

export function SeverityBadge({
  severity,
  className,
}: {
  severity: string
  className?: string
}) {
  const key = (
    severity in SEVERITY_STYLES ? severity : 'info'
  ) as keyof typeof SEVERITY_STYLES
  return (
    <Badge variant="outline" className={cn(SEVERITY_STYLES[key], className)}>
      {SEVERITY_LABELS[key]}
    </Badge>
  )
}

const GREEN =
  'border-emerald-700/50 bg-emerald-700/10 text-emerald-800 dark:border-emerald-400/40 dark:text-emerald-300'
const RED =
  'border-red-700/50 bg-red-700/10 text-red-800 dark:border-red-400/40 dark:text-red-300'
const BLUE =
  'border-sky-700/50 bg-sky-700/10 text-sky-800 dark:border-sky-400/40 dark:text-sky-300'
const GREY = 'border-border bg-muted text-muted-foreground'

/* Every status the backend writes to reviews.status and webhook_deliveries.status. */
const STATUS_STYLES: Record<string, string> = {
  completed: GREEN,
  pong: GREEN,
  failed: RED,
  timed_out: RED,
  running: BLUE,
  queued: BLUE,
  received: BLUE,
  superseded: GREY,
  interrupted: GREY,
  duplicate: GREY,
  ignored: GREY,
  skipped_draft: GREY,
  skipped_bot: GREY,
  expired: GREY,
}

const STATUS_LABELS: Record<string, string> = {
  completed: 'Completed',
  pong: 'Ping answered',
  failed: 'Failed',
  timed_out: 'Timed out',
  running: 'Running',
  queued: 'Queued',
  received: 'Received',
  superseded: 'Superseded',
  interrupted: 'Interrupted',
  duplicate: 'Duplicate',
  ignored: 'Ignored',
  skipped_draft: 'Draft, skipped',
  skipped_bot: 'Bot author, skipped',
  expired: 'Expired',
}

/** The state of a review run. Lives here so both badges share one palette. */
export function ReviewStatusBadge({ status }: { status: string }) {
  return (
    <Badge
      variant="outline"
      className={STATUS_STYLES[status] ?? 'border-border bg-muted'}
    >
      {STATUS_LABELS[status] ?? status}
    </Badge>
  )
}
