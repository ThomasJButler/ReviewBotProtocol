import { describe, expect, it } from 'vitest'

import { formatWhen, isGitHubUrl, pullRequestUrl } from '@/lib/utils'

describe('isGitHubUrl', () => {
  it.each([
    ['https://github.com/octocat/repo/pull/1', true],
    ['https://api.github.com/x', true],
    ['http://github.com/x', true],
    ['https://evilgithub.com/x', false],
    ['https://github.com.evil.example/x', false],
    ['javascript:alert(1)', false],
    ['//github.com/x', false],
    ['', false],
    [null, false],
  ])('%s -> %s', (url, expected) => {
    expect(isGitHubUrl(url)).toBe(expected)
  })
})

describe('pullRequestUrl', () => {
  it('encodes each path segment', () => {
    expect(pullRequestUrl('octocat/repo', 7)).toBe(
      'https://github.com/octocat/repo/pull/7'
    )
    expect(pullRequestUrl('octo cat/re?po', 7.9)).toBe(
      'https://github.com/octo%20cat/re%3Fpo/pull/7'
    )
  })
})

describe('formatWhen', () => {
  it('renders UTC regardless of the offset given', () => {
    expect(formatWhen('2026-09-03T16:05:00+00:00')).toBe('03 Sept 2026, 16:05')
    expect(formatWhen('2026-09-03T17:05:00+01:00')).toBe('03 Sept 2026, 16:05')
  })
  it('never throws on rubbish', () => {
    expect(formatWhen(null)).toBe('none')
    expect(formatWhen('not a date')).toBe('none')
  })
})
