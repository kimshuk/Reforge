import { SegmentIndexEntry } from '../analyze/transcript.sanitizer';

export type LlmProvider = 'openai' | 'gemini' | 'claude';
export type TranscriptType = 'youtube' | 'manual';

export interface LlmOptions {
  provider: LlmProvider;
  model: string;
  temperature: number;
  maxOutputTokens?: number;
}

export interface LlmRequestOverrides {
  provider?: unknown;
  model?: unknown;
  temperature?: unknown;
  maxOutputTokens?: unknown;
}

export interface CategoryKeyword {
  term: string;
  brief: string;
  level1: string;
  level2: string;
  level3: string;
  source: {
    type: TranscriptType;
    ref: string;
  };
}

export interface Category {
  title: string;
  keywords: CategoryKeyword[];
}

export interface CategoryAnalysis {
  sourceType: TranscriptType;
  categories: Category[];
}

export interface GenerateAnalysisInput {
  transcriptText: string;
  transcriptType: TranscriptType;
  targetLanguage: string;
  youtubeUrl?: string;
  segmentIndex?: SegmentIndexEntry[];
  options: LlmOptions;
}

export interface ProviderPrompt {
  system: string;
  user: string;
}

export interface JsonSchemaFormat {
  name: string;
  strict: boolean;
  schema: Record<string, unknown>;
}

export interface LlmProviderAdapter {
  readonly provider: LlmProvider;
  generateJson(
    prompt: ProviderPrompt,
    options: LlmOptions,
    schema?: JsonSchemaFormat,
  ): Promise<string>;
}

export interface AnalysisWithLlmSettings extends CategoryAnalysis {
  llm: LlmOptions;
}

export interface TranscriptSummaryMoment {
  time: string;
  seconds: number;
  title: string;
  summary: string;
  url?: string;
}

export interface TranscriptSummary {
  summary: string;
  timestamps: TranscriptSummaryMoment[];
}

export interface SummaryWithLlmSettings extends TranscriptSummary {
  llm: LlmOptions;
  rawText?: string;
}

export interface GenerateSummaryInput {
  transcriptText: string;
  transcriptType: TranscriptType;
  targetLanguage: string;
  youtubeUrl?: string;
  segmentIndex?: SegmentIndexEntry[];
  options: LlmOptions;
  includeRawText?: boolean;
}

export interface TopicChunkBoundary {
  startSegmentId: string;
  endSegmentId: string;
  title: string;
  summary: string;
  signalLevel: 'high' | 'medium' | 'low' | 'off_topic';
}

export interface CandidateClippingOutput {
  kind: string;
  title: string;
  text: string;
  brief: string;
  simpleExplanation: string;
  contextualExplanation: string;
  detailedExplanation: string;
  signalLevel: 'high' | 'medium' | 'low';
  sourceRefs: Array<{
    startSegmentId: string;
    endSegmentId: string;
    timestamp: string;
    text: string;
  }>;
}
