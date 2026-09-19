import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { ReviewStatusBadge } from '@/components/severity-badge'

describe('ReviewStatusBadge', () => {
  it('labels an expired delivery rather than printing the raw status', () => {
    const html = renderToStaticMarkup(<ReviewStatusBadge status="expired" />)
    expect(html).toContain('Expired')
  })
})
