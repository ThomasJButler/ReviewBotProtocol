'use client'

import { useRouter } from 'next/navigation'

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

const ALL = '__all__'

/** Writes the choice into the query string; the page is re-rendered on the
 * server with the new filter. */
export function RepositoryFilter({
  repositories,
  selected,
}: {
  repositories: string[]
  selected?: string
}) {
  const router = useRouter()

  return (
    <div className="flex items-center gap-2">
      <label htmlFor="repository-filter" className="text-sm">
        Repository
      </label>
      <Select
        value={selected || ALL}
        onValueChange={value =>
          router.push(
            value === ALL ? '/' : `/?repository=${encodeURIComponent(value)}`
          )
        }
      >
        <SelectTrigger id="repository-filter" className="min-w-56">
          {/* The label is given explicitly so the server-rendered trigger
              already reads correctly, before Radix hydrates. */}
          <SelectValue placeholder="All repositories">
            {selected || 'All repositories'}
          </SelectValue>
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>All repositories</SelectItem>
          {repositories.map(repository => (
            <SelectItem key={repository} value={repository}>
              {repository}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}
