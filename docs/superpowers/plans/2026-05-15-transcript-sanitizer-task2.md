# TranscriptSanitizerService Task 2: Snippet Flattening, Sorting, and Segment Builder

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the helper functions and internal types that transform a raw `RawSnippet[]` into a segmented `{ llmTranscriptText, segmentIndex }` result — the building blocks `sanitize()` will call in Task 3.

**Architecture:** All additions go into `backend-nest/src/analyze/transcript.sanitizer.ts`. Exported: `SegmentOptions`. Module-private: `DEFAULTS`, `CleanSnippet`, `ActiveSegment`, `formatTimestamp`, `sanitizeSnippetList`, `shouldSplitSegment`, `buildSegments`. The `sanitize()` stub is not wired yet — that's Task 3.

**Tech Stack:** TypeScript, NestJS. No new test files — all private functions will be exercised indirectly via `sanitize()` integration tests in Task 3.

---

### Task 1: Add types and constants

**Files:**
- Modify: `backend-nest/src/analyze/transcript.sanitizer.ts`

- [ ] **Step 1: Add `SegmentOptions`, `DEFAULTS`, `CleanSnippet`, `ActiveSegment` to the file**

Insert the following block after the `RawSnippet` interface (after line 10) and before `stripBracketNoise`:

```typescript
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
```

The file from the top through the new block should now look like:

```typescript
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
```

- [ ] **Step 2: Verify build passes**

```bash
cd backend-nest && npm run build
```

Expected: zero TypeScript errors.

- [ ] **Step 3: Commit**

```bash
git add backend-nest/src/analyze/transcript.sanitizer.ts
git commit -m "feat(sanitizer): add SegmentOptions, DEFAULTS, and internal snippet/segment types"
```

---

### Task 2: Add `formatTimestamp` and `sanitizeSnippetList`

**Files:**
- Modify: `backend-nest/src/analyze/transcript.sanitizer.ts`

- [ ] **Step 1: Add `formatTimestamp` and `sanitizeSnippetList` after `normalizeText`**

Insert the following two functions after `normalizeText` (currently ending around line 40) and before `SegmentIndexEntry`:

```typescript
function formatTimestamp(totalSeconds: number): string {
  const seconds = Math.max(0, Math.floor(Number(totalSeconds) || 0));
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;

  if (h > 0) {
    return `${String(h)}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  }

  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

function sanitizeSnippetList(rawSnippets: RawSnippet[]): CleanSnippet[] {
  const snippets: CleanSnippet[] = [];

  for (const item of rawSnippets) {
    const startSec = Number(item?.start);
    if (!Number.isFinite(startSec) || startSec < 0) {
      continue;
    }

    const durationSec = Number(item?.duration);
    const safeDuration =
      Number.isFinite(durationSec) && durationSec > 0 ? durationSec : 0;
    const text = normalizeText(item?.text);

    if (!text) {
      continue;
    }

    snippets.push({
      startSec,
      endSec: startSec + safeDuration,
      text,
    });
  }

  snippets.sort((a, b) => a.startSec - b.startSec);
  return snippets;
}
```

- [ ] **Step 2: Verify build passes**

```bash
cd backend-nest && npm run build
```

Expected: zero TypeScript errors.

- [ ] **Step 3: Commit**

```bash
git add backend-nest/src/analyze/transcript.sanitizer.ts
git commit -m "feat(sanitizer): add formatTimestamp and sanitizeSnippetList"
```

---

### Task 3: Add `shouldSplitSegment` and `buildSegments`

**Files:**
- Modify: `backend-nest/src/analyze/transcript.sanitizer.ts`

- [ ] **Step 1: Add `shouldSplitSegment` and `buildSegments` after `sanitizeSnippetList`**

Insert the following two functions after `sanitizeSnippetList` and before `SegmentIndexEntry`:

```typescript
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

  if (nextDuration > cfg.maxSegmentSeconds || nextChars > cfg.maxSegmentChars) {
    const readyToSplit =
      segment.duration >= cfg.minSegmentSeconds ||
      segment.charCount >= cfg.minSegmentChars;
    if (readyToSplit) {
      return true;
    }

    if (
      nextDuration > cfg.hardMaxSegmentSeconds ||
      nextChars > cfg.hardMaxSegmentChars
    ) {
      return true;
    }
  }

  return false;
}

function buildSegments(
  snippets: CleanSnippet[],
  options?: SegmentOptions,
): { llmTranscriptText: string; segmentIndex: SegmentIndexEntry[] } {
  const cfg: Required<SegmentOptions> = { ...DEFAULTS, ...options };
  const finalized: Array<{ startSec: number; endSec: number; text: string }> = [];
  let current: ActiveSegment | null = null;

  const finalizeCurrent = () => {
    if (!current || !current.parts.length) {
      current = null;
      return;
    }

    const text = current.parts.join(' ').replace(/\s+/g, ' ').trim();
    if (!text) {
      current = null;
      return;
    }

    finalized.push({ startSec: current.startSec, endSec: current.endSec, text });
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

  const segmentIndex: SegmentIndexEntry[] = finalized.map((seg, i) => ({
    id: `S${String(i + 1).padStart(3, '0')}`,
    startSec: seg.startSec,
    endSec: seg.endSec,
    text: seg.text,
  }));

  const llmTranscriptText = segmentIndex
    .map((seg) => `${seg.id} | ${formatTimestamp(seg.startSec)} | ${seg.text}`)
    .join('\n');

  return { llmTranscriptText, segmentIndex };
}
```

- [ ] **Step 2: Verify the complete file looks correct**

The full `backend-nest/src/analyze/transcript.sanitizer.ts` should now be:

```typescript
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

function formatTimestamp(totalSeconds: number): string {
  const seconds = Math.max(0, Math.floor(Number(totalSeconds) || 0));
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;

  if (h > 0) {
    return `${String(h)}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  }

  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

function sanitizeSnippetList(rawSnippets: RawSnippet[]): CleanSnippet[] {
  const snippets: CleanSnippet[] = [];

  for (const item of rawSnippets) {
    const startSec = Number(item?.start);
    if (!Number.isFinite(startSec) || startSec < 0) {
      continue;
    }

    const durationSec = Number(item?.duration);
    const safeDuration =
      Number.isFinite(durationSec) && durationSec > 0 ? durationSec : 0;
    const text = normalizeText(item?.text);

    if (!text) {
      continue;
    }

    snippets.push({
      startSec,
      endSec: startSec + safeDuration,
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

  if (nextDuration > cfg.maxSegmentSeconds || nextChars > cfg.maxSegmentChars) {
    const readyToSplit =
      segment.duration >= cfg.minSegmentSeconds ||
      segment.charCount >= cfg.minSegmentChars;
    if (readyToSplit) {
      return true;
    }

    if (
      nextDuration > cfg.hardMaxSegmentSeconds ||
      nextChars > cfg.hardMaxSegmentChars
    ) {
      return true;
    }
  }

  return false;
}

function buildSegments(
  snippets: CleanSnippet[],
  options?: SegmentOptions,
): { llmTranscriptText: string; segmentIndex: SegmentIndexEntry[] } {
  const cfg: Required<SegmentOptions> = { ...DEFAULTS, ...options };
  const finalized: Array<{ startSec: number; endSec: number; text: string }> = [];
  let current: ActiveSegment | null = null;

  const finalizeCurrent = () => {
    if (!current || !current.parts.length) {
      current = null;
      return;
    }

    const text = current.parts.join(' ').replace(/\s+/g, ' ').trim();
    if (!text) {
      current = null;
      return;
    }

    finalized.push({ startSec: current.startSec, endSec: current.endSec, text });
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

  const segmentIndex: SegmentIndexEntry[] = finalized.map((seg, i) => ({
    id: `S${String(i + 1).padStart(3, '0')}`,
    startSec: seg.startSec,
    endSec: seg.endSec,
    text: seg.text,
  }));

  const llmTranscriptText = segmentIndex
    .map((seg) => `${seg.id} | ${formatTimestamp(seg.startSec)} | ${seg.text}`)
    .join('\n');

  return { llmTranscriptText, segmentIndex };
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
```

- [ ] **Step 3: Verify build passes**

```bash
cd backend-nest && npm run build
```

Expected: zero TypeScript errors.

- [ ] **Step 4: Verify existing tests still pass**

```bash
cd backend-nest && npm test
```

Expected: 6 tests pass, 0 failures.

- [ ] **Step 5: Commit**

```bash
git add backend-nest/src/analyze/transcript.sanitizer.ts
git commit -m "feat(sanitizer): add shouldSplitSegment and buildSegments"
```
