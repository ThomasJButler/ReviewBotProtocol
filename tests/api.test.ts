import { afterEach, describe, expect, it, vi } from 'vitest'

// server-only throws outside a React server context; stub it for the unit test.
vi.mock('server-only', () => ({}))

describe('lib/api guards', () => {
  const env = { ...process.env }
  afterEach(() => {
    process.env = { ...env }
    vi.resetModules()
  })

  it('refuses to send the token anywhere but loopback', async () => {
    process.env.LOCAL_API_TOKEN = 't'
    process.env.BACKEND_URL = 'http://backend.example.com:8000'
    const api = await import('@/lib/api')
    const result = await api.getStatus()
    expect(result.ok).toBe(false)
    if (!result.ok) expect(result.kind).toBe('config')
  })

  it('reports a missing token as configuration', async () => {
    delete process.env.LOCAL_API_TOKEN
    const api = await import('@/lib/api')
    const result = await api.listReviews({})
    expect(result.ok).toBe(false)
    if (!result.ok) expect(result.kind).toBe('config')
  })

  it('rejects review ids that are not uuids before building a URL', async () => {
    process.env.LOCAL_API_TOKEN = 't'
    process.env.BACKEND_URL = 'http://127.0.0.1:8000'
    const api = await import('@/lib/api')
    expect(api.isReviewId('../../status')).toBe(false)
    expect(api.isReviewId('750b2b76-a663-454a-95a0-957f0b22eee3')).toBe(true)
    const result = await api.getReview('..%2F..%2Fstatus')
    expect(result.ok).toBe(false)
    if (!result.ok) expect(result.status).toBe(404)
  })
})
