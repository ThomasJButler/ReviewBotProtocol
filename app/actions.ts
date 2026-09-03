'use server'

import { revalidatePath } from 'next/cache'

import {
  getStatus,
  isReviewId,
  setFeedback,
  type ApiResult,
  type Status,
} from '@/lib/api'

/** Re-fetch the reviews table. Used by the refresh button, which is a plain
 * form submit and so works without client JavaScript. */
export async function refreshReviews(): Promise<void> {
  revalidatePath('/')
}

/** Re-fetch the status page. */
export async function refreshStatus(): Promise<void> {
  revalidatePath('/status')
}

/** Read the queue and Ollama health for the header chip. The chip polls this
 * every 30 seconds while the tab is visible; the backend token stays here. */
export async function readStatus(): Promise<ApiResult<Status>> {
  return getStatus()
}

/** Record whether a review was useful. Stored locally by the backend. */
export async function recordFeedback(
  reviewId: string,
  useful: boolean | null
): Promise<{ ok: boolean; message?: string }> {
  // Types are erased at runtime and anyone who can reach the port can call this.
  if (!isReviewId(reviewId)) return { ok: false, message: 'Not a review id.' }
  if (useful !== true && useful !== false && useful !== null) {
    return { ok: false, message: 'Not a valid answer.' }
  }
  const result = await setFeedback(reviewId, useful)
  if (!result.ok) return { ok: false, message: result.message }
  revalidatePath(`/reviews/${reviewId}`)
  revalidatePath('/')
  return { ok: true }
}
