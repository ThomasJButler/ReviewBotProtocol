import { Skeleton } from '@/components/ui/skeleton'

export default function Loading() {
  return (
    <div className="space-y-8" aria-busy="true" aria-label="Loading reviews">
      <div className="space-y-2">
        <Skeleton className="h-8 w-40" />
        <Skeleton className="h-4 w-80" />
      </div>
      <div className="flex flex-wrap items-center gap-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-8 w-28" />
        <Skeleton className="ml-auto h-7 w-48 rounded-full" />
      </div>
      <div className="space-y-2 rounded-lg border border-border p-4">
        {Array.from({ length: 8 }).map((_, index) => (
          <Skeleton key={index} className="h-9 w-full" />
        ))}
      </div>
    </div>
  )
}
