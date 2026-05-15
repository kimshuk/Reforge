import { Injectable } from '@nestjs/common';

const BRACKET_NOISE_PATTERN =
  /^(music|applause|laugh(?:ter)?|noise|silence|bgm|audience|clap|박수|웃음|음악)$/i;

export interface RawSnippet {
  start: number;
  duration?: number;
  text?: string;
}

export interface SegmentOptions {
  minSegmentSeconds?: number;
  maxSegmentSeconds?: number;
  hardMaxSegmentSeconds?: number;
  minSegmentChars?: number;
  maxSegmentChars?: number;
  hardMaxSegmentChars?: number;
  pauseSplitSeconds?: number;
}

const DEFAULTS: Required<SegmentOptions> = {
  minSegmentSeconds: 20,
  maxSegmentSeconds: 35,
  hardMaxSegmentSeconds: 45,
  minSegmentChars: 180,
  maxSegmentChars: 320,
  hardMaxSegmentChars: 420,
  pauseSplitSeconds: 2.5,
};

interface CleanSnippet {
  startSec: number;
  endSec: number;
  text: string;
}

interface ActiveSegment {
  startSec: number;
  endSec: number;
  parts: string[];
  charCount: number;
  duration: number;
}

export function stripBracketNoise(text: string): string {
  return text
    .replace(/\[([^\]]{1,30})\]/g, (match: string, content: string) =>
      BRACKET_NOISE_PATTERN.test(content.trim()) ? ' ' : match,
    )
    .replace(/\(([^)]{1,30})\)/g, (match: string, content: string) =>
      BRACKET_NOISE_PATTERN.test(content.trim()) ? ' ' : match,
    );
}

function normalizeText(input: string | undefined): string {
  if (typeof input !== 'string') {
    return '';
  }

  let text = input;
  text = text.replace(/^\s*>+\s*/, ' ');
  text = stripBracketNoise(text);
  text = text.replace(/ㅋ{3,}/g, '');
  text = text.replace(/ㅎ{3,}/g, '');
  text = text.replace(/([!?.,~])\1{2,}/g, '$1$1');
  text = text.replace(/\s+/g, ' ').trim();

  if (/^[>|~\-_=.,!?]+$/.test(text)) {
    return '';
  }

  return text;
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
