import { Skeleton } from '@/components/ui/skeleton'

export default function Loading() {
  return (
    <div className="space-y-8" aria-busy="true" aria-label="Loading the review">
      <Skeleton className="h-4 w-28" />
      <div className="space-y-3">
        <Skeleton className="h-8 w-96 max-w-full" />
        <Skeleton className="h-4 w-72 max-w-full" />
        <Skeleton className="h-5 w-40" />
      </div>
      <div className="grid grid-cols-2 gap-4 rounded-lg border border-border p-4 sm:grid-cols-3 lg:grid-cols-6">
        {Array.from({ length: 6 }).map((_, index) => (
          <Skeleton key={index} className="h-10 w-full" />
        ))}
      </div>
      <Skeleton className="h-9 w-64" />
      <div className="space-y-3">
        {Array.from({ length: 3 }).map((_, index) => (
          <Skeleton key={index} className="h-32 w-full rounded-lg" />
        ))}
      </div>
    </div>
  )
}
