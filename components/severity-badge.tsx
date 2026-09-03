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

const STATUS_STYLES: Record<string, string> = {
  completed:
    'border-emerald-700/50 bg-emerald-700/10 text-emerald-800 dark:border-emerald-400/40 dark:text-emerald-300',
  failed:
    'border-red-700/50 bg-red-700/10 text-red-800 dark:border-red-400/40 dark:text-red-300',
  running:
    'border-sky-700/50 bg-sky-700/10 text-sky-800 dark:border-sky-400/40 dark:text-sky-300',
}

const STATUS_LABELS: Record<string, string> = {
  completed: 'Completed',
  failed: 'Failed',
  running: 'Running',
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
