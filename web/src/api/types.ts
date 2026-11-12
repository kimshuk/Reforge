export interface AnalyzeSource {
  type: 'youtube' | 'manual'
  ref: string
}

export interface ExternalSource {
  citationId: string
  title: string
  url: string
}

export interface AnalyzeKeyword {
  term: string
  candidateClippingId: string
  brief: string
  level1: string
  level2: string
  level3: string
  source: AnalyzeSource
  sources: AnalyzeSource[]
  level2CitationIds: string[]
  level3CitationIds: string[]
  externalSources: ExternalSource[]
}

export interface AnalyzeCategory {
  categoryId: string
  title: string
  keywords: AnalyzeKeyword[]
}

export interface AnalyzeResponse {
  transcriptId: string
  sourceType: 'youtube' | 'manual'
  categories: AnalyzeCategory[]
  expiresInSeconds: number
  llm: Record<string, unknown>
  videoId?: string | null
}

export type ExplanationLevel = 1 | 2 | 3
