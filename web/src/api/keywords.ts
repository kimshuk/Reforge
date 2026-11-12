import type { AnalyzeKeyword, ExplanationLevel, ExternalSource } from './types'

export function levelText(keyword: AnalyzeKeyword, level: ExplanationLevel): string {
  return { 1: keyword.level1, 2: keyword.level2, 3: keyword.level3 }[level]
}

export function nextLevel(level: ExplanationLevel): ExplanationLevel {
  return level === 1 ? 2 : 3
}

export function visibleExternalSources(
  keyword: AnalyzeKeyword,
  level: ExplanationLevel,
): ExternalSource[] {
  const ids: string[] = { 1: [], 2: keyword.level2CitationIds, 3: keyword.level3CitationIds }[level]
  return keyword.externalSources.filter((source) => ids.includes(source.citationId))
}
