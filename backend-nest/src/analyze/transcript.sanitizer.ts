import { Injectable } from '@nestjs/common';

const BRACKET_NOISE_PATTERN =
  /^(music|applause|laugh(?:ter)?|noise|silence|bgm|audience|clap|박수|웃음|음악)$/i;

export function stripBracketNoise(text: string): string {
  return text
    .replace(/\[([^\]]{1,30})\]/g, (match: string, content: string) =>
      BRACKET_NOISE_PATTERN.test(content.trim()) ? ' ' : match,
    )
    .replace(/\(([^)]{1,30})\)/g, (match: string, content: string) =>
      BRACKET_NOISE_PATTERN.test(content.trim()) ? ' ' : match,
    );
}

export interface SegmentIndexEntry {
  id: string; // e.g. "S001", "S002"
  startSec: number;
  endSec: number;
  text: string;
}

export interface SanitizedTranscript {
  llmTranscriptText: string;
  segmentIndex: SegmentIndexEntry[];
  cleanedSnippetCount: number;
}

@Injectable()
export class TranscriptSanitizer {
  sanitize() {
    throw new Error('not implemented');
  }
}
