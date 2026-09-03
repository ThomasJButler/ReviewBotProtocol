import * as React from 'react'

/**
 * Renders the review body exactly as the backend posted it, without ever
 * putting model text into HTML. The backend's sanitiser strips tags and keeps
 * links only to github.com, and this renderer understands only the subset it
 * emits: headings, bullet and numbered lists, rules, paragraphs, inline code,
 * bold, and links. Anything else stays as plain text.
 */

const INLINE = /(`[^`]+`)|(\*\*[^*]+\*\*)|(\[[^\]\n]+\]\([^()\s]+\))/g

function isGitHubUrl(raw: string): boolean {
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

function inline(text: string, key: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = []
  let cursor = 0
  let n = 0

  for (const match of text.matchAll(INLINE)) {
    const start = match.index ?? 0
    if (start > cursor) nodes.push(text.slice(cursor, start))
    const token = match[0]
    const id = `${key}-i${n}`

    if (token.startsWith('`')) {
      nodes.push(<code key={id}>{token.slice(1, -1)}</code>)
    } else if (token.startsWith('**')) {
      nodes.push(<strong key={id}>{token.slice(2, -2)}</strong>)
    } else {
      const split = token.indexOf('](')
      const label = token.slice(1, split)
      const href = token.slice(split + 2, -1)
      // Links off github.com are shown as their label and nothing else.
      nodes.push(
        isGitHubUrl(href) ? (
          <a key={id} href={href} target="_blank" rel="noopener noreferrer">
            {label}
          </a>
        ) : (
          label
        )
      )
    }

    cursor = start + token.length
    n += 1
  }

  if (cursor < text.length) nodes.push(text.slice(cursor))
  return nodes
}

const HEADING = /^(#{1,6})\s+(.*)$/
const RULE = /^(-{3,}|\*{3,})$/
const BULLET = /^[-*]\s+(.*)$/
const NUMBER = /^\d+\.\s+(.*)$/

export function PostedBody({ body }: { body: string }) {
  const lines = body.replace(/\r\n/g, '\n').split('\n')
  const blocks: React.ReactNode[] = []
  let i = 0

  while (i < lines.length) {
    const line = lines[i]
    const key = `b${i}`

    if (line.trim() === '') {
      i += 1
      continue
    }

    if (RULE.test(line.trim())) {
      blocks.push(<hr key={key} />)
      i += 1
      continue
    }

    const heading = HEADING.exec(line)
    if (heading) {
      // h1 belongs to the page, so the body starts at h2.
      const Tag = (heading[1].length <= 2 ? 'h2' : 'h3') as 'h2' | 'h3'
      blocks.push(<Tag key={key}>{inline(heading[2], key)}</Tag>)
      i += 1
      continue
    }

    const isBullet = BULLET.test(line)
    const isNumber = !isBullet && NUMBER.test(line)
    if (isBullet || isNumber) {
      const pattern = isBullet ? BULLET : NUMBER
      const items: string[] = []
      while (i < lines.length) {
        const item = pattern.exec(lines[i])
        if (!item) break
        items.push(item[1])
        i += 1
      }
      const List = isBullet ? 'ul' : 'ol'
      blocks.push(
        <List key={key}>
          {items.map((item, n) => (
            <li key={`${key}-${n}`}>{inline(item, `${key}-${n}`)}</li>
          ))}
        </List>
      )
      continue
    }

    const paragraph: string[] = []
    while (i < lines.length) {
      const next = lines[i]
      if (
        next.trim() === '' ||
        RULE.test(next.trim()) ||
        HEADING.test(next) ||
        BULLET.test(next) ||
        NUMBER.test(next)
      ) {
        break
      }
      paragraph.push(next.trim())
      i += 1
    }
    const text = paragraph.join(' ')
    if (text) blocks.push(<p key={key}>{inline(text, key)}</p>)
  }

  return <div className="posted-body">{blocks}</div>
}
