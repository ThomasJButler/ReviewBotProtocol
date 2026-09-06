import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import {
  ReviewProgressBar,
  progressLabel,
  visibleProgress,
} from '@/components/review-progress'
import type { ReviewProgress } from '@/lib/api'

const reviewing: ReviewProgress = {
  phase: 'review',
  done: 7,
  total: 25,
  file: 'app/routes/webhook.py',
}

describe('progressLabel', () => {
  it('names the phase, the count and the file', () => {
    expect(progressLabel(reviewing)).toBe(
      'Reviewing 7 of 25: app/routes/webhook.py'
    )
    expect(
      progressLabel({ ...reviewing, phase: 'cross-examine', done: 3 })
    ).toBe('Cross-examining 3 of 25: app/routes/webhook.py')
  })

  it('drops the file when there is none', () => {
    expect(progressLabel({ ...reviewing, file: null })).toBe(
      'Reviewing 7 of 25'
    )
  })

  it('says Finishing once both phases are done', () => {
    expect(
      progressLabel({ phase: 'done', done: 25, total: 25, file: null })
    ).toBe('Finishing')
  })
})

describe('visibleProgress', () => {
  it('shows progress only while the review is running', () => {
    expect(visibleProgress('running', reviewing)).toBe(reviewing)
    expect(
      visibleProgress('completed', {
        phase: 'done',
        done: 25,
        total: 25,
        file: null,
      })
    ).toBeNull()
    expect(visibleProgress('running', null)).toBeNull()
    expect(visibleProgress('running', { ...reviewing, total: 0 })).toBeNull()
  })
})

describe('ReviewProgressBar', () => {
  it('renders the line and a bar carrying the same numbers', () => {
    const html = renderToStaticMarkup(
      <ReviewProgressBar progress={reviewing} />
    )
    expect(html).toContain('Reviewing 7 of 25: app/routes/webhook.py')
    expect(html).toContain('role="progressbar"')
    expect(html).toContain('aria-valuenow="7"')
    expect(html).toContain('aria-valuemin="0"')
    expect(html).toContain('aria-valuemax="25"')
    expect(html).toContain('aria-label="Files done"')
  })

  it('renders nothing without progress or a total', () => {
    expect(renderToStaticMarkup(<ReviewProgressBar progress={null} />)).toBe('')
    expect(
      renderToStaticMarkup(<ReviewProgressBar progress={undefined} />)
    ).toBe('')
    expect(
      renderToStaticMarkup(
        <ReviewProgressBar progress={{ ...reviewing, total: 0 }} />
      )
    ).toBe('')
  })

  it('keeps a silly count inside the bar', () => {
    const html = renderToStaticMarkup(
      <ReviewProgressBar progress={{ ...reviewing, done: 99 }} />
    )
    expect(html).toContain('aria-valuenow="25"')
    expect(html).toContain('Reviewing 25 of 25')
  })
})
