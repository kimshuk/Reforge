import { describe, expect, it } from 'vitest'
import { levelText, nextLevel, visibleExternalSources } from './keywords'
import type { AnalyzeKeyword } from './types'

const source = { type: 'youtube', ref: 'https://youtu.be/x?t=1s' } as const
const keyword: AnalyzeKeyword = {
  term: 'Codex',
  candidateClippingId: 'a',
  brief: 'Brief',
  level1: 'One',
  level2: 'Two',
  level3: 'Three',
  source,
  sources: [source],
  level2CitationIds: ['C1'],
  level3CitationIds: ['C2'],
  externalSources: [
    { citationId: 'C1', title: 'First', url: 'https://example.com/1' },
    { citationId: 'C2', title: 'Second', url: 'https://example.com/2' },
    { citationId: 'C3', title: 'Unused', url: 'https://example.com/3' },
  ],
}

describe('levelText', () => {
  it('returns the text for each level', () => {
    expect([1, 2, 3].map((level) => levelText(keyword, level as 1 | 2 | 3))).toEqual([
      'One',
      'Two',
      'Three',
    ])
  })
})

describe('nextLevel', () => {
  it('steps forward and stops at the last level', () => {
    expect(nextLevel(1)).toBe(2)
    expect(nextLevel(2)).toBe(3)
    expect(nextLevel(3)).toBe(3)
  })
})

describe('visibleExternalSources', () => {
  it('shows nothing at level 1', () => {
    expect(visibleExternalSources(keyword, 1)).toEqual([])
  })

  it('shows only the citations of the current level', () => {
    expect(visibleExternalSources(keyword, 2).map((item) => item.citationId)).toEqual(['C1'])
    expect(visibleExternalSources(keyword, 3).map((item) => item.citationId)).toEqual(['C2'])
  })
})
