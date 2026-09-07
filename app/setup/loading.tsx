import { Skeleton } from '@/components/ui/skeleton'

export default function Loading() {
  return (
    <div className="space-y-8" aria-busy="true" aria-label="Loading setup">
      <div className="space-y-2">
        <Skeleton className="h-8 w-32" />
        <Skeleton className="h-4 w-96 max-w-full" />
      </div>
      {Array.from({ length: 5 }).map((_, index) => (
        <Skeleton key={index} className="h-40 w-full rounded-lg" />
      ))}
    </div>
  )
}
