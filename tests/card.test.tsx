import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { CardTitle } from '@/components/ui/card'

describe('CardTitle', () => {
  it('is a div unless told otherwise, as shadcn ships it', () => {
    const html = renderToStaticMarkup(<CardTitle>Limits</CardTitle>)
    expect(html).toMatch(/^<div data-slot="card-title"/)
    expect(html).toContain('Limits')
  })

  it('renders a heading when a card names a section of the page', () => {
    const html = renderToStaticMarkup(<CardTitle as="h2">Limits</CardTitle>)
    expect(html).toMatch(/^<h2 data-slot="card-title" class="/)
    expect(html).toContain('font-heading')
  })
})
