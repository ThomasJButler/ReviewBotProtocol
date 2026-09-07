import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

const WHEN = new Intl.DateTimeFormat('en-GB', {
  day: '2-digit',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
  timeZone: 'UTC',
})

/** Timestamps are rendered in UTC so the server and the browser always agree. */
export function formatWhen(iso: string | null): string {
  if (!iso) return 'none'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return 'none'
  return WHEN.format(date)
}

export function formatDuration(seconds: number | null): string {
  if (seconds === null || seconds === undefined) return 'none'
  if (seconds < 60) return `${seconds.toFixed(1)} s`
  const minutes = Math.floor(seconds / 60)
  return `${minutes} m ${Math.round(seconds - minutes * 60)} s`
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(0)} kB`
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`
  return `${(bytes / 1024 ** 3).toFixed(1)} GB`
}

export function shortSha(sha: string | null): string {
  return sha ? sha.slice(0, 7) : 'none'
}

/** github.com is the only host this dashboard ever links to. */
export function pullRequestUrl(repository: string, prNumber: number): string {
  const [owner = '', name = ''] = repository.split('/')
  return `https://github.com/${encodeURIComponent(owner)}/${encodeURIComponent(name)}/pull/${Math.trunc(prNumber)}`
}

/** True for http(s) links to github.com or a subdomain of it. */
export function isGitHubUrl(raw: string | null | undefined): boolean {
  if (!raw) return false
  let url: URL
  try {
    url = new URL(raw)
  } catch {
    return false
  }
  if (url.protocol !== 'https:' && url.protocol !== 'http:') return false
  const host = url.hostname.toLowerCase()
  return host === 'github.com' || host.endsWith('.github.com')
}
