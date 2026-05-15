# TranscriptSanitizerService — Task 1: Types & normalizeText

**Date:** 2026-05-15
**Scope:** `backend-nest/src/analyze/transcript.sanitizer.ts` only

## Goal

Add the `RawSnippet` input interface and implement the `normalizeText` helper. The stub already has `BRACKET_NOISE_PATTERN`, `stripBracketNoise`, and the output types (`SegmentIndexEntry`, `SanitizedTranscript`). Nothing else changes in this task.

## New Interface: `RawSnippet`

Exported. Represents a single snippet from the Python `youtube-transcript-api` output.

```typescript
export interface RawSnippet {
  start: number;
  duration?: number;
  text?: string;
}
```

`duration` and `text` are optional because the downstream code is already defensive about missing or non-finite values.

## New Function: `normalizeText`

Module-private (not exported). Accepts a raw snippet text string, returns a cleaned string. Returns `""` for inputs that normalize to nothing useful — callers must drop empty results.

Steps in order:

1. Return `""` immediately if input is not a string.
2. Strip leading `>` quote markers: `/^\s*>+\s*/g` → `" "`.
3. Call `stripBracketNoise`.
4. Remove excessive Korean onomatopoeia runs: `ㅋ{3+}` → `""`, `ㅎ{3+}` → `""`. This **intentionally diverges** from the Express source (which collapsed to two) — these expressions carry no semantic value for LLM input.
5. Collapse punctuation runs of 3+ to two: `([!?.,~])\1{2,}` → `"$1$1"`. Preserves tone signal, removes excess noise.
6. Normalize whitespace: collapse runs with `/\s+/g` → `" "`, then trim.
7. Return `""` if the result matches `/^[>|~\-_=.,!?]+$/` (purely decorative symbols).

## Testing

`normalizeText` is module-private and not directly testable from the spec file. Its behavior will be covered indirectly through `sanitize` integration tests added in Task 3. No new tests in this task.

## What Does Not Change

- `sanitize()` method — stays as a throw-stub until Task 3.
- All other files (`analyze.module.ts`, etc.) — untouched.
- `stripBracketNoise` — already implemented and tested; no changes.
