import { cn } from '@/lib/utils'
import type { ReviewProgress } from '@/lib/api'

/* The phases the backend reports, in the words the dashboard shows. */
const PHASE_VERBS: Record<string, string> = {
  review: 'Reviewing',
  'cross-examine': 'Cross-examining',
}

/** Files finished so far, never below zero or past the total. */
export function filesDone(progress: ReviewProgress): number {
  if (!Number.isFinite(progress.done)) return 0
  return Math.min(Math.max(Math.trunc(progress.done), 0), progress.total)
}

/** One plain line: what the run is doing, how far it has got, on which file. */
export function progressLabel(progress: ReviewProgress): string {
  if (progress.phase === 'done') return 'Finishing'
  const verb = PHASE_VERBS[progress.phase] ?? 'Working through'
  const line = `${verb} ${filesDone(progress)} of ${progress.total}`
  return progress.file ? `${line}: ${progress.file}` : line
}

/** The progress worth showing on a row or a page: a run still going that has
 * reported how many files it has. Everything else shows nothing, so reviews
 * from before the backend reported progress look exactly as they did. */
export function visibleProgress(
  status: string,
  progress: ReviewProgress | null | undefined
): ReviewProgress | null {
  if (status !== 'running' || !progress) return null
  return progress.total > 0 ? progress : null
}

/**
 * How far a running review has got. The count is spelled out in words next to
 * the bar, so the bar is never the only thing carrying the answer.
 */
export function ReviewProgressBar({
  progress,
  className,
}: {
  progress: ReviewProgress | null | undefined
  className?: string
}) {
  if (!progress || !(progress.total > 0)) return null
  const done = filesDone(progress)
  return (
    <div className={cn('space-y-1.5', className)}>
      <p className="text-sm break-all text-muted-foreground">
        {progressLabel(progress)}
      </p>
      <div
        role="progressbar"
        aria-label="Files done"
        aria-valuemin={0}
        aria-valuemax={progress.total}
        aria-valuenow={done}
        aria-valuetext={`${done} of ${progress.total} files`}
        className="h-1.5 w-full overflow-hidden rounded-full bg-muted"
      >
        <div
          className="h-full rounded-full bg-foreground/50"
          style={{ width: `${((done / progress.total) * 100).toFixed(1)}%` }}
        />
      </div>
    </div>
  )
}
