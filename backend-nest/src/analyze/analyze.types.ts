import { LlmRequestOverrides, TranscriptType } from '../llm/llm.types';

export interface AnalyzeSource extends LlmRequestOverrides {
  type: TranscriptType;
  targetLanguage: string;
  title?: string;
  youtubeUrl?: string;
  text?: string;
}

export interface YoutubeTranscriptResult {
  videoId: string;
  transcriptText: string;
  transcriptSnippets: unknown[];
  languageCode: string | null;
  language: string | null;
  isGenerated: boolean | null;
}
