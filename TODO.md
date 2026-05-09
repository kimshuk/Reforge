# Daily Tasks — 2026-05-09
## Focus: NestJS Migration — Step 5: TranscriptSanitizerService

## Today's 3 Tasks

- [ ] **Define output shape and implement per-snippet text normalization**
  - Declare TypeScript interfaces for the sanitizer's input (raw snippet array from Python) and its output (`llmTranscriptText`, `segmentIndex`, `cleanedSnippetCount`) so callers have a typed contract to program against
  - Port the bracket-noise stripping logic: content like `[music]`, `[applause]`, `(laughter)` should be replaced with whitespace, while unrecognized brackets are left intact — the Express-side `BRACKET_NOISE_PATTERN` and `stripBracketNoise` define the exact match list (English and Korean terms)
  - Collapse excessively repeated Korean onomatopoeia (`ㅋㅋㅋ...` → `ㅋㅋ`, `ㅎㅎㅎ...` → `ㅎㅎ`) and repeated punctuation runs (`!!!` → `!!`), then drop lines that are purely decorative symbols — cross-reference `normalizeText` in `backend/src/services/transcriptSanitizer.js`

- [ ] **Implement snippet flattening, sorting, and segment builder**
  - Flatten potentially nested raw snippet arrays into a flat list, filter out items with invalid or negative `start` values, normalize each item's text, and sort the result by `startSec` — cross-reference `flattenRawSnippets` and `sanitizeSnippetList`
  - Port the two-phase segment grouping: accumulate consecutive snippets into a running segment, and split into a new segment when a natural pause ≥ 2.5 s appears between snippets, or when soft duration/character thresholds (35 s / 320 chars) are exceeded and the segment is already mature, or when hard limits (45 s / 420 chars) are hit regardless — cross-reference `shouldSplitSegment` and `buildSegments`
  - Assign sequential IDs (`S001`, `S002`, …) to each finalized segment, join its constituent snippet texts with a single space, and format `llmTranscriptText` as one `"S### | MM:SS | text"` line per segment — this is the exact format the LLM prompt expects

- [ ] **Wire the public `sanitize` method, export `formatTimestamp`, and verify build**
  - Replace the throw-stub `sanitize()` with the real method signature: accepts a raw snippet array and returns the typed `SanitizedTranscript` shape by calling the flattening and segment-building helpers in sequence
  - Export `formatTimestamp` (seconds → `MM:SS` or `H:MM:SS`) from the service as a named export or public method — `LlmService` will need it in Step 6 to resolve YouTube source timestamp citations back to segment start times
  - Run `npm run build` in `backend-nest/` and confirm zero TypeScript errors before calling this step done

## Migration Progress
**Completed steps:**
- 1 — Bootstrap NestJS scaffold (health module, main.ts, tsconfig strict mode)
- 2 — Project structure (analyze/ and common/ stubs, AnalyzeModule wired into AppModule)
- 3 — AppException class (common/app.exception.ts)
- 4 — YoutubeService (Python subprocess, URL → transcript text, error classification)

**Current step:** 5 — TranscriptSanitizerService (transcript.sanitizer.ts is still a throw-stub)

**Remaining steps:**
- 6 — LlmService (OpenRouter call + structured output: categories + keywords)
- 7 — AnalyzeService (orchestrate URL → youtube → sanitize → llm, or text → sanitize → llm)
- 8 — AnalyzeController (POST /analyze with SSE streaming)
- 9 — AppExceptionFilter (finalize { error: { code, message } } envelope + global registration)

## Why These Tasks
The three tasks follow the natural compile dependency order within the sanitizer — types first, then pure helper functions, then the public method that ties them together — so each task leaves the codebase in a buildable state and the next task has a stable foundation to build on.
