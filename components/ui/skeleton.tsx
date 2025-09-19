import { cn } from '@/lib/utils'

function Skeleton({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        [
          'animate-pulse rounded-md bg-gradient-to-r from-card-surface/60 via-card-surface/80 to-card-surface/60',
          'bg-[length:200%_100%] relative overflow-hidden',
        ],
        className
      )}
      style={{
        background:
          'linear-gradient(90deg, rgba(26,26,26,0.6) 25%, rgba(26,26,26,0.8) 50%, rgba(26,26,26,0.6) 75%)',
        backgroundSize: '200% 100%',
        animation: 'shimmer 2s infinite',
      }}
      {...props}
    >
      {/* Shimmer overlay effect */}
      <div className="absolute inset-0 bg-gradient-to-r from-transparent via-matrix-green/5 to-transparent transform -skew-x-12 animate-[shimmer_2s_infinite]" />
    </div>
  )
}

// Pre-built skeleton variants for common use cases
const CardSkeleton = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) => (
  <div
    className={cn('glass-effect rounded-2xl p-6 space-y-4', className)}
    {...props}
  >
    <div className="flex items-center space-x-4">
      <Skeleton className="h-12 w-12 rounded-full" />
      <div className="space-y-2">
        <Skeleton className="h-4 w-[200px]" />
        <Skeleton className="h-4 w-[150px]" />
      </div>
    </div>
    <Skeleton className="h-4 w-full" />
    <Skeleton className="h-4 w-[80%]" />
    <Skeleton className="h-4 w-[60%]" />
  </div>
)

const ReviewSkeleton = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn('space-y-6', className)} {...props}>
    {/* Summary skeleton */}
    <CardSkeleton />

    {/* Issues skeleton */}
    {[1, 2, 3].map(i => (
      <div key={i} className="glass-effect rounded-xl p-4 space-y-3">
        <div className="flex items-center gap-2">
          <Skeleton className="h-5 w-16 rounded-full" />
          <Skeleton className="h-4 w-[250px]" />
        </div>
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-[85%]" />
        <Skeleton className="h-3 w-[20%]" />
      </div>
    ))}
  </div>
)

const TableSkeleton = ({
  rows = 5,
  columns = 4,
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & {
  rows?: number
  columns?: number
}) => (
  <div className={cn('space-y-3', className)} {...props}>
    {/* Header */}
    <div
      className="grid gap-4"
      style={{ gridTemplateColumns: `repeat(${columns}, 1fr)` }}
    >
      {Array.from({ length: columns }).map((_, i) => (
        <Skeleton key={i} className="h-4 w-full" />
      ))}
    </div>

    {/* Rows */}
    {Array.from({ length: rows }).map((_, rowIndex) => (
      <div
        key={rowIndex}
        className="grid gap-4"
        style={{ gridTemplateColumns: `repeat(${columns}, 1fr)` }}
      >
        {Array.from({ length: columns }).map((_, colIndex) => (
          <Skeleton key={colIndex} className="h-4 w-full" />
        ))}
      </div>
    ))}
  </div>
)

const CodeSkeleton = ({
  lines = 8,
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { lines?: number }) => (
  <div className={cn('space-y-2 font-mono', className)} {...props}>
    {Array.from({ length: lines }).map((_, i) => (
      <div key={i} className="flex items-center gap-4">
        <Skeleton className="h-4 w-8" /> {/* Line number */}
        <Skeleton
          className="h-4"
          style={{ width: `${Math.random() * 60 + 40}%` }} // Random width for realistic code
        />
      </div>
    ))}
  </div>
)

export { Skeleton, CardSkeleton, ReviewSkeleton, TableSkeleton, CodeSkeleton }
