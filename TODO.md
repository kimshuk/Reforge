# Daily Tasks — 2026-05-12
## Focus: NestJS Migration — Step 5: TranscriptSanitizerService

## Today's 3 Tasks

- [ ] **Implement `normalizeText` and `formatTimestamp` helpers**
  - `normalizeText` cleans a single snippet's text string: strip leading `>` quote markers, run `stripBracketNoise`, collapse Korean onomatopoeia runs (`ㅋ`, `ㅎ`) and repeated punctuation down to two characters, normalize whitespace, and return an empty string for lines that contain only decorative symbols — cross-reference `normalizeText` in `backend/src/services/transcriptSanitizer.js` for the exact regex rules
  - `formatTimestamp` converts a raw seconds value to `MM:SS` (or `H:MM:SS` for videos over an hour); it must clamp NaN and negative inputs to zero so callers never need to guard — this function will also be imported directly by `LlmService` in Step 6 to format timestamps in the prompt, so it must be exported at the module level
  - Add focused unit tests covering non-string input, empty string, Korean collapsing, repeated-punctuation collapsing, sub-hour and super-hour timestamp formatting; passing tests are the completion gate

- [ ] **Implement the snippet flattening, filtering, and segment-building pipeline**
  - Port `flattenRawSnippets` (recursively unwraps nested arrays into a flat list of snippet objects) and `sanitizeSnippetList` (discards snippets with non-finite or negative `start`, normalizes each snippet's text via `normalizeText`, drops empties, sorts survivors by `startSec`) — these two together produce the clean, ordered input the segment builder expects
  - Port `shouldSplitSegment` and `buildSegments` using the threshold constants from the Express backend: pause split at 2.5 s; soft caps at 35 s / 320 chars with a maturity guard at 20 s / 180 chars; hard caps at 45 s / 420 chars — the split logic exists to keep segments semantically coherent, not arbitrary time slices
  - `buildSegments` must assign sequential IDs (`S001`, `S002`, …), join each segment's snippets with a single space, and produce an `llmTranscriptText` string formatted as one `"S### | MM:SS | text"` line per segment — this exact string is what the LLM prompt in Step 6 will receive

- [ ] **Wire `sanitize()`, export `formatTimestamp`, and verify clean build**
  - Replace the throw-stub `sanitize()` with the real implementation: accept a raw snippet array, pass it through `sanitizeSnippetList` then `buildSegments`, and return a fully typed `SanitizedTranscript` (`llmTranscriptText`, `segmentIndex`, `cleanedSnippetCount`) — this is the only public entry point that `AnalyzeService` (Step 7) will call
  - Confirm `formatTimestamp` is exported at the module level (not just an internal helper), so `LlmService` can import it in Step 6 without coupling to the full `TranscriptSanitizer` class
  - Run `npm run build` in `backend-nest/` and confirm zero TypeScript errors; run `npm test` to confirm the existing `stripBracketNoise` spec and all new tests pass — a clean build and green tests are the completion gate for Step 5

## Migration Progress
**Completed steps:**
- 1 — Bootstrap NestJS scaffold (health module, main.ts, tsconfig strict mode)
- 2 — Project structure (analyze/ and common/ stubs, AnalyzeModule wired into AppModule)
- 3 — AppException class (common/app.exception.ts)
- 4 — YoutubeService (Python subprocess, URL → transcript text, error classification)

**Current step:** 5 — TranscriptSanitizerService (interfaces + `stripBracketNoise` done; `normalizeText`, `formatTimestamp`, snippet pipeline, and `sanitize()` still outstanding)

**Remaining steps:**
- 6 — LlmService (OpenRouter call + structured output: categories + keywords)
- 7 — AnalyzeService (orchestrate URL → youtube → sanitize → llm, or text → sanitize → llm)
- 8 — AnalyzeController (POST /analyze with SSE streaming)
- 9 — AppExceptionFilter (finalize { error: { code, message } } envelope + global registration)

## Why These Tasks
Step 5 is the blocking dependency for all downstream steps — nothing in Steps 6–9 can be built until the sanitizer produces a valid `SanitizedTranscript`. The three tasks are ordered by internal dependency: pure helpers first (no imports from this file), then the pipeline that consumes them, then the public `sanitize()` method and `formatTimestamp` export that seal the contract for future callers.
