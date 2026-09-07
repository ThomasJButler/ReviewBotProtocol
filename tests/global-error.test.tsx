import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import GlobalError from '@/app/global-error'

describe('GlobalError', () => {
  it('paints its own document, since the root layout is what failed', () => {
    const error = Object.assign(new Error('layout exploded'), {
      digest: 'abc123',
    })
    const html = renderToStaticMarkup(
      <GlobalError error={error} reset={() => undefined} />
    )
    expect(html).toMatch(/^<html lang="en-GB"><head><\/head><body/)
    expect(html).toContain('could not render this page')
    expect(html).toContain('layout exploded')
    expect(html).toContain('Digest abc123')
    expect(html).toContain('<button type="button"')
  })

  it('says so when the error carries no message', () => {
    const html = renderToStaticMarkup(
      <GlobalError error={new Error('')} reset={() => undefined} />
    )
    expect(html).toContain('No message was given.')
  })
})
