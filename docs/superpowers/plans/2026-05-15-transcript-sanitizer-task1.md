# TranscriptSanitizerService Task 1: Types & normalizeText Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the `RawSnippet` input interface and `normalizeText` helper to the NestJS `TranscriptSanitizer` stub.

**Architecture:** Both additions go into `transcript.sanitizer.ts`. `RawSnippet` is exported for use by callers. `normalizeText` is module-private and called internally by `sanitizeSnippetList` (added in Task 2). No other files change.

**Tech Stack:** TypeScript, NestJS, Jest (no new tests in this task — `normalizeText` is private and will be exercised indirectly via `sanitize` in Task 3)

---

### Task 1: Add `RawSnippet` interface

**Files:**
- Modify: `backend-nest/src/analyze/transcript.sanitizer.ts`

- [ ] **Step 1: Add the interface after the `BRACKET_NOISE_PATTERN` constant**

Open `backend-nest/src/analyze/transcript.sanitizer.ts`. Insert this block between the `BRACKET_NOISE_PATTERN` constant and the `stripBracketNoise` function:

```typescript
export interface RawSnippet {
  start: number;
  duration?: number;
  text?: string;
}
```

The file should look like this after the edit:

```typescript
import { Injectable } from '@nestjs/common';

const BRACKET_NOISE_PATTERN =
  /^(music|applause|laugh(?:ter)?|noise|silence|bgm|audience|clap|박수|웃음|음악)$/i;

export interface RawSnippet {
  start: number;
  duration?: number;
  text?: string;
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

- [ ] **Step 2: Verify build passes**

```bash
cd backend-nest && npm run build
```

Expected: zero TypeScript errors. The new interface is a pure addition with no downstream impact yet.

---

### Task 2: Add `normalizeText` function

**Files:**
- Modify: `backend-nest/src/analyze/transcript.sanitizer.ts`

- [ ] **Step 1: Add `normalizeText` after `stripBracketNoise`**

Insert this function between `stripBracketNoise` and the `SegmentIndexEntry` interface:

```typescript
function normalizeText(input: string | undefined): string {
  if (typeof input !== 'string') {
    return '';
  }

  let text = input;
  text = text.replace(/^\s*>+\s*/g, ' ');
  text = stripBracketNoise(text);
  text = text.replace(/(ㅋ){3,}/g, '');
  text = text.replace(/(ㅎ){3,}/g, '');
  text = text.replace(/([!?.,~])\1{2,}/g, '$1$1');
  text = text.replace(/\s+/g, ' ').trim();

  if (/^[>|~\-_=.,!?]+$/.test(text)) {
    return '';
  }

  return text;
}
```

The complete file should now look like this:

```typescript
import { Injectable } from '@nestjs/common';

const BRACKET_NOISE_PATTERN =
  /^(music|applause|laugh(?:ter)?|noise|silence|bgm|audience|clap|박수|웃음|음악)$/i;

export interface RawSnippet {
  start: number;
  duration?: number;
  text?: string;
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
  text = text.replace(/^\s*>+\s*/g, ' ');
  text = stripBracketNoise(text);
  text = text.replace(/(ㅋ){3,}/g, '');
  text = text.replace(/(ㅎ){3,}/g, '');
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
```

- [ ] **Step 2: Verify build passes**

```bash
cd backend-nest && npm run build
```

Expected: zero TypeScript errors.

- [ ] **Step 3: Commit**

```bash
git add backend-nest/src/analyze/transcript.sanitizer.ts
git commit -m "feat(sanitizer): add RawSnippet interface and normalizeText helper"
```
