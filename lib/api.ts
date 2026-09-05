import 'server-only'

/**
 * The only place the frontend talks to the backend. Everything here runs on
 * the server: BACKEND_URL and LOCAL_API_TOKEN are read from process.env and
 * are never exposed to the browser (no NEXT_PUBLIC_ prefix anywhere).
 */

export type Severity = 'critical' | 'high' | 'medium' | 'low' | 'info'

export interface SkippedFile {
  path: string
  reason: string
}

export interface Review {
  id: string
  repository: string
  pr_number: number
  pr_title: string | null
  head_sha: string | null
  is_fork: boolean
  status: string
  model: string | null
  cross_model: string | null
  cross_added: number
  cross_refuted: number
  files_total: number
  files_reviewed: number
  files_skipped: number
  skipped: SkippedFile[]
  findings_count: number
  severity_counts: Partial<Record<Severity, number>>
  findings_dropped: number
  redactions: number
  prompt_tokens: number
  output_tokens: number
  duration_seconds: number | null
  error_message: string | null
  comment_url: string | null
  useful: boolean | null
  created_at: string | null
  completed_at: string | null
}

export interface Finding {
  id: string
  path: string
  line: number
  category: string
  source_model: string | null
  cross_verdict: 'real' | 'false_positive' | null
  cross_reason: string | null
  severity: Severity
  title: string
  evidence: string | null
  recommendation: string | null
  confidence: number | null
}

export interface ReviewDetail extends Review {
  /** The body exactly as it was posted to GitHub, in the markdown subset the
   * backend emits. Rendered by components/posted-body.tsx. */
  summary: string | null
  findings: Finding[]
}

export interface ReviewList {
  items: Review[]
  total: number
  repositories: string[]
}

export interface LoadedModel {
  name: string | null
  size_vram: number | null
  context_length: number | null
}

export interface Status {
  version: string
  model: string
  cross_model: string | null
  ollama: {
    base_url?: string
    cross_model?: string
    cross_model_present?: boolean
    reachable: boolean
    model: string
    model_present: boolean
    loaded: LoadedModel[]
    error?: string
  }
  database: boolean
  queue: {
    depth: number
    alive: boolean
    abandoned: number
    current: { repository: string; pr_number: number; head_sha: string } | null
  }
  limits: {
    max_files_per_review: number
    max_patch_bytes: number
    review_timeout_seconds: number
    num_ctx: number
  }
}

export interface Delivery {
  delivery_id: string
  event: string
  action: string | null
  repository: string | null
  pr_number: number | null
  head_sha: string | null
  status: string
  review_id: string | null
  received_at: string | null
}

export interface DeliveryList {
  items: Delivery[]
}

/** Why a call failed, in terms the operator can act on. */
export type ApiFailure = {
  ok: false
  kind: 'config' | 'unreachable' | 'auth' | 'http'
  message: string
  status?: number
}

export type ApiResult<T> = { ok: true; data: T } | ApiFailure

const DEFAULT_BACKEND_URL = 'http://127.0.0.1:8000'

const LOOPBACK = new Set(['127.0.0.1', 'localhost', '[::1]', '::1'])

export function backendUrl(): string {
  return (process.env.BACKEND_URL || DEFAULT_BACKEND_URL).replace(/\/+$/, '')
}

/** The token is only ever sent to a backend on this machine. */
export function backendUrlProblem(): string | null {
  let url: URL
  try {
    url = new URL(backendUrl())
  } catch {
    return `BACKEND_URL is not a valid URL: ${backendUrl()}`
  }
  if (url.protocol !== 'http:' && url.protocol !== 'https:') {
    return `BACKEND_URL must be http or https, not ${url.protocol}`
  }
  if (!LOOPBACK.has(url.hostname)) {
    return `BACKEND_URL points at ${url.hostname}; the dashboard only sends LOCAL_API_TOKEN to this machine (127.0.0.1 or localhost)`
  }
  return null
}

const REVIEW_ID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

export function isReviewId(value: unknown): value is string {
  return typeof value === 'string' && REVIEW_ID.test(value)
}

async function call<T>(
  path: string,
  init: RequestInit = {}
): Promise<ApiResult<T>> {
  const token = process.env.LOCAL_API_TOKEN
  if (!token) {
    return {
      ok: false,
      kind: 'config',
      message:
        'LOCAL_API_TOKEN is not set for the dashboard, so it cannot reach the backend API.',
    }
  }
  const problem = backendUrlProblem()
  if (problem) {
    return { ok: false, kind: 'config', message: problem }
  }

  let response: Response
  try {
    response = await fetch(`${backendUrl()}${path}`, {
      ...init,
      cache: 'no-store',
      signal: AbortSignal.timeout(10_000),
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: 'application/json',
        ...(init.body ? { 'Content-Type': 'application/json' } : {}),
        ...init.headers,
      },
    })
  } catch {
    return {
      ok: false,
      kind: 'unreachable',
      message: `No answer from the backend at ${backendUrl()}.`,
    }
  }

  if (response.status === 401 || response.status === 503) {
    return {
      ok: false,
      kind: 'auth',
      message:
        'The backend refused the local token. Check that LOCAL_API_TOKEN matches the value in backend/.env.',
      status: response.status,
    }
  }
  if (!response.ok) {
    return {
      ok: false,
      kind: 'http',
      message: `The backend answered ${response.status} for ${path}.`,
      status: response.status,
    }
  }

  try {
    return { ok: true, data: (await response.json()) as T }
  } catch {
    return {
      ok: false,
      kind: 'http',
      message: `The backend answered ${path} with something that is not JSON.`,
      status: response.status,
    }
  }
}

export function listReviews(params: {
  repository?: string
  limit?: number
  offset?: number
}): Promise<ApiResult<ReviewList>> {
  const query = new URLSearchParams()
  if (params.repository) query.set('repository', params.repository)
  query.set('limit', String(params.limit ?? 50))
  query.set('offset', String(params.offset ?? 0))
  return call<ReviewList>(`/api/reviews?${query.toString()}`)
}

export function getReview(id: string): Promise<ApiResult<ReviewDetail>> {
  if (!isReviewId(id)) {
    return Promise.resolve({
      ok: false,
      kind: 'http',
      message: 'Not a review id.',
      status: 404,
    })
  }
  return call<ReviewDetail>(`/api/reviews/${id}`)
}

export function getStatus(): Promise<ApiResult<Status>> {
  return call<Status>('/api/status')
}

export function listDeliveries(limit = 20): Promise<ApiResult<DeliveryList>> {
  return call<DeliveryList>(`/api/deliveries?limit=${limit}`)
}

export function setFeedback(
  id: string,
  useful: boolean | null
): Promise<ApiResult<{ id: string; useful: boolean | null }>> {
  if (!isReviewId(id)) {
    return Promise.resolve({
      ok: false,
      kind: 'http',
      message: 'Not a review id.',
      status: 404,
    })
  }
  if (useful !== true && useful !== false && useful !== null) {
    return Promise.resolve({
      ok: false,
      kind: 'http',
      message: 'Not a valid answer.',
      status: 400,
    })
  }
  return call(`/api/reviews/${id}/feedback`, {
    method: 'POST',
    body: JSON.stringify({ useful }),
  })
}
