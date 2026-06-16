import { Injectable } from '@nestjs/common';

const BRACKET_NOISE_PATTERN =
  /^(music|applause|laugh(?:ter)?|noise|silence|bgm|audience|clap|박수|웃음|음악)$/i;

const DEFAULTS = {
  minSegmentSeconds: 20,
  maxSegmentSeconds: 35,
  hardMaxSegmentSeconds: 45,
  minSegmentChars: 180,
  maxSegmentChars: 320,
  hardMaxSegmentChars: 420,
  pauseSplitSeconds: 2.5,
};

export interface RawSnippet {
  start?: unknown;
  duration?: unknown;
  text?: unknown;
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

interface CleanSnippet {
  startSec: number;
  endSec: number;
  rawText: string;
  text: string;
}

interface ActiveSegment {
  startSec: number;
  endSec: number;
  parts: string[];
  charCount: number;
  duration: number;
}

export interface SegmentIndexEntry {
  id: string;
  startSec: number;
  endSec: number;
  text: string;
}

export interface CleanedTranscriptSegment {
  sequence: number;
  startSec: number;
  endSec: number;
  rawText: string;
  text: string;
}

export interface SanitizedTranscript {
  llmTranscriptText: string;
  segmentIndex: SegmentIndexEntry[];
  sourceSegments: CleanedTranscriptSegment[];
  cleanedSnippetCount: number;
}

export function formatTimestamp(totalSeconds: number): string {
  const seconds = Math.max(
    0,
    Number.isFinite(totalSeconds) ? Math.floor(totalSeconds) : 0,
  );
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;

  if (h > 0) {
    return `${String(h)}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  }

  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
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

function flattenRawSnippets(input: unknown, out: RawSnippet[] = []): RawSnippet[] {
  if (Array.isArray(input)) {
    for (const item of input) {
      flattenRawSnippets(item, out);
    }
    return out;
  }

  if (input && typeof input === 'object') {
    out.push(input as RawSnippet);
  }

  return out;
}

export function normalizeText(input: unknown): string {
  if (typeof input !== 'string') {
    return '';
  }

  let text = input;
  text = text.replace(/^\s*>+\s*/g, ' ');
  text = stripBracketNoise(text);
  text = text.replace(/ㅋ{3,}/g, 'ㅋㅋ');
  text = text.replace(/ㅎ{3,}/g, 'ㅎㅎ');
  text = text.replace(/([!?.,~])\1{2,}/g, '$1$1');
  text = text.replace(/\s+/g, ' ').trim();

  if (/^[>|~\-_=.,!?]+$/.test(text)) {
    return '';
  }

  return text;
}

function sanitizeSnippetList(rawSnippets: unknown): CleanSnippet[] {
  const snippets: CleanSnippet[] = [];

  for (const item of flattenRawSnippets(rawSnippets)) {
    const startSec = Number(item.start);
    if (!Number.isFinite(startSec) || startSec < 0) {
      continue;
    }

    const durationSec = Number(item.duration);
    const safeDuration =
      Number.isFinite(durationSec) && durationSec > 0 ? durationSec : 0;
    const rawText = typeof item.text === 'string' ? item.text.trim() : '';
    const text = normalizeText(item.text);

    if (!text) {
      continue;
    }

    snippets.push({
      startSec,
      endSec: startSec + safeDuration,
      rawText,
      text,
    });
  }

  snippets.sort((a, b) => a.startSec - b.startSec);
  return snippets;
}

function shouldSplitSegment(
  segment: ActiveSegment,
  next: CleanSnippet,
  cfg: Required<SegmentOptions>,
): boolean {
  const pause = next.startSec - segment.endSec;
  if (pause > cfg.pauseSplitSeconds) {
    return true;
  }

  const nextEnd = Math.max(segment.endSec, next.endSec);
  const nextDuration = nextEnd - segment.startSec;
  const nextChars = segment.charCount + 1 + next.text.length;

  if (nextDuration <= cfg.maxSegmentSeconds && nextChars <= cfg.maxSegmentChars) {
    return false;
  }

  const readyToSplit =
    segment.duration >= cfg.minSegmentSeconds ||
    segment.charCount >= cfg.minSegmentChars;

  return (
    readyToSplit ||
    nextDuration > cfg.hardMaxSegmentSeconds ||
    nextChars > cfg.hardMaxSegmentChars
  );
}

function buildSegments(
  snippets: CleanSnippet[],
  options: SegmentOptions = {},
): Pick<SanitizedTranscript, 'llmTranscriptText' | 'segmentIndex'> {
  const cfg: Required<SegmentOptions> = { ...DEFAULTS, ...options };
  const segments: Array<{ startSec: number; endSec: number; text: string }> = [];
  let current: ActiveSegment | null = null;

  const finalizeCurrent = () => {
    if (!current?.parts.length) {
      current = null;
      return;
    }

    const text = current.parts.join(' ').replace(/\s+/g, ' ').trim();
    if (text) {
      segments.push({
        startSec: current.startSec,
        endSec: current.endSec,
        text,
      });
    }
    current = null;
  };

  for (const snippet of snippets) {
    if (!current) {
      current = {
        startSec: snippet.startSec,
        endSec: snippet.endSec,
        parts: [snippet.text],
        charCount: snippet.text.length,
        duration: Math.max(0, snippet.endSec - snippet.startSec),
      };
      continue;
    }

    if (shouldSplitSegment(current, snippet, cfg)) {
      finalizeCurrent();
      current = {
        startSec: snippet.startSec,
        endSec: snippet.endSec,
        parts: [snippet.text],
        charCount: snippet.text.length,
        duration: Math.max(0, snippet.endSec - snippet.startSec),
      };
      continue;
    }

    current.parts.push(snippet.text);
    current.endSec = Math.max(current.endSec, snippet.endSec);
    current.charCount += 1 + snippet.text.length;
    current.duration = Math.max(0, current.endSec - current.startSec);
  }

  finalizeCurrent();

  const segmentIndex = segments.map((segment, index) => ({
    id: `S${String(index + 1).padStart(3, '0')}`,
    startSec: segment.startSec,
    endSec: segment.endSec,
    text: segment.text,
  }));

  const llmTranscriptText = segmentIndex
    .map((segment) => `${segment.id} | ${formatTimestamp(segment.startSec)} | ${segment.text}`)
    .join('\n');

  return { llmTranscriptText, segmentIndex };
}

@Injectable()
export class TranscriptSanitizer {
  sanitize(rawSnippets: unknown, options: SegmentOptions = {}): SanitizedTranscript {
    const cleanedSnippets = sanitizeSnippetList(rawSnippets);
    const sourceSegments = cleanedSnippets.map((snippet, index) => ({
      sequence: index,
      startSec: snippet.startSec,
      endSec: snippet.endSec,
      rawText: snippet.rawText,
      text: snippet.text,
    }));

    return {
      ...buildSegments(cleanedSnippets, options),
      sourceSegments,
      cleanedSnippetCount: cleanedSnippets.length,
    };
  }
}
