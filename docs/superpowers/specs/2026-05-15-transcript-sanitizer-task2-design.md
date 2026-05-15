# TranscriptSanitizerService — Task 2: Snippet Flattening, Sorting, and Segment Builder

**Date:** 2026-05-15
**Scope:** `backend-nest/src/analyze/transcript.sanitizer.ts` only

## Goal

Add the internal helper functions and types needed to transform a raw `RawSnippet[]` into a fully segmented `{ llmTranscriptText, segmentIndex }` result. The public `sanitize()` method is still wired in Task 3 — this task delivers the building blocks.

## New Exported Interface: `SegmentOptions`

All fields optional. Callers pass a partial object; `buildSegments` merges it with `DEFAULTS`.

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
```

## Module-Private Constants and Types

**`DEFAULTS`** — module-private constant with the 6 threshold values:

```typescript
const DEFAULTS: Required<SegmentOptions> = {
  minSegmentSeconds: 20,
  maxSegmentSeconds: 35,
  hardMaxSegmentSeconds: 45,
  minSegmentChars: 180,
  maxSegmentChars: 320,
  hardMaxSegmentChars: 420,
  pauseSplitSeconds: 2.5,
};
```

**`CleanSnippet`** — module-private. Output of `sanitizeSnippetList`, input to `buildSegments`.

```typescript
interface CleanSnippet {
  startSec: number;
  endSec: number;
  text: string;
}
```

**`ActiveSegment`** — module-private. Accumulator used inside `buildSegments`.

```typescript
interface ActiveSegment {
  startSec: number;
  endSec: number;
  parts: string[];
  charCount: number;
  duration: number;
}
```

## New Module-Private Functions

### `formatTimestamp(totalSeconds: number): string`

Converts seconds to `MM:SS` or `H:MM:SS`. Direct port from the Express source. Module-private here — Task 3 exports it as a named export.

### `sanitizeSnippetList(rawSnippets: RawSnippet[]): CleanSnippet[]`

No recursive flattening — Python always returns a flat list. Steps:
1. For each item, coerce `start` to a number; skip if non-finite or negative.
2. Coerce `duration` to a number; use `0` if non-finite or ≤ 0.
3. Call `normalizeText(item.text)`; skip item if result is empty.
4. Push `{ startSec, endSec: startSec + duration, text }`.
5. Sort by `startSec` ascending before returning.

### `shouldSplitSegment(segment: ActiveSegment, next: CleanSnippet, cfg: Required<SegmentOptions>): boolean`

Direct port of the JS split logic:
1. If pause between `segment.endSec` and `next.startSec` ≥ `cfg.pauseSplitSeconds` → split.
2. Compute `nextDuration` and `nextChars` if the snippet were added.
3. If either exceeds the soft threshold (`maxSegmentSeconds` / `maxSegmentChars`) AND the segment is already mature (≥ `minSegmentSeconds` or ≥ `minSegmentChars`) → split.
4. If either exceeds the hard threshold (`hardMaxSegmentSeconds` / `hardMaxSegmentChars`) → split unconditionally.
5. Otherwise → don't split.

### `buildSegments(snippets: CleanSnippet[], options?: SegmentOptions): { llmTranscriptText: string; segmentIndex: SegmentIndexEntry[] }`

1. Merge `options` with `DEFAULTS` to produce a `Required<SegmentOptions>` config.
2. Iterate snippets, accumulating into an `ActiveSegment`. On each snippet, call `shouldSplitSegment`; if true, finalize the current segment and start a new one.
3. Finalize the last open segment after the loop.
4. Finalization: join `parts` with `" "`, collapse whitespace, discard if empty.
5. Assign sequential IDs: `S001`, `S002`, …
6. Build `llmTranscriptText` as one line per segment: `"S### | MM:SS | text"` using `formatTimestamp(startSec)`.
7. Return `{ llmTranscriptText, segmentIndex }`.

## Testing

All four functions are module-private. Their behavior will be covered indirectly through `sanitize()` integration tests added in Task 3. No new tests in this task.

## What Does Not Change

- `sanitize()` method — stays as a throw-stub until Task 3.
- All other files — untouched.
- Task 1 additions (`RawSnippet`, `stripBracketNoise`, `normalizeText`) — untouched.
