# Daily Tasks — 2026-05-16
## Focus: NestJS Migration — Step 5: TranscriptSanitizerService

## Today's 3 Tasks

- [ ] **Implement and export `formatTimestamp`**
  - Add `formatTimestamp` as a module-level export (not a class method) that converts a raw seconds value to `MM:SS` for videos under an hour, or `H:MM:SS` for videos at or beyond 3600 seconds — the exact string it produces is embedded in every segment line sent to the LLM, so the format must match the Express backend precisely
  - Guard against bad inputs by clamping via `Math.max(0, Math.floor(Number(input) || 0))`, ensuring the function never throws or returns `NaN`/`Infinity` even when called with `null`, `undefined`, or a non-numeric value
  - Add unit tests for the four cases: sub-hour, super-hour, zero, and a non-numeric input; all tests green confirms this export is ready for `buildSegments` and for `LlmService` to import directly

- [ ] **Implement the snippet pipeline: flatten, filter, sort, and segment**
  - Port `flattenRawSnippets` (recursively collapses arbitrarily nested arrays into a flat list of snippet objects) and `sanitizeSnippetList` (rejects snippets whose `start` is non-finite or negative, normalizes each snippet's text through `normalizeText`, drops results with empty text, computes `endSec` as `start + duration`, and sorts the survivors ascending by `startSec`) — these two together produce the clean ordered list that `buildSegments` consumes
  - Port `shouldSplitSegment` and `buildSegments` using the threshold constants from the Express backend: a pause greater than 2.5 s between snippets triggers an unconditional split; soft caps at 35 s / 320 chars trigger a split only when the segment has already matured past 20 s / 180 chars; hard caps at 45 s / 420 chars force a split regardless of maturity — these rules keep segments semantically coherent rather than cutting at arbitrary boundaries
  - `buildSegments` must produce sequential IDs (`S001`, `S002`, …), join each segment's parts with a single space, and format the final `llmTranscriptText` as one `"S### | MM:SS | text"` line per segment using `formatTimestamp` — this exact string is what `AnalyzeService` will pass to `LlmService` in the next steps

- [ ] **Wire `sanitize()` and verify clean build**
  - Replace the `sanitize()` throw-stub with a real implementation: accept a `RawSnippet[]`, run it through `sanitizeSnippetList` then `buildSegments`, and return a `SanitizedTranscript` (`llmTranscriptText`, `segmentIndex`, `cleanedSnippetCount`) — this is the only public method `AnalyzeService` will call, so its return shape must match the interface already defined in the file
  - Confirm `formatTimestamp` remains exported at module level (not enclosed inside the class), so `LlmService` can import it as a standalone utility without depending on the `TranscriptSanitizer` injectable
  - Run `npm run build` in `backend-nest/` and confirm zero TypeScript errors; run `npm test` to confirm all existing and new tests pass — a clean build and green tests are the completion gate for Step 5 and unlock Step 6 (LlmService)

## Migration Progress
**Completed steps:**
- 1 — Bootstrap NestJS scaffold (health module, main.ts, tsconfig strict mode)
- 2 — Project structure (analyze/ and common/ stubs, AnalyzeModule wired into AppModule)
- 3 — AppException class (common/app.exception.ts)
- 4 — YoutubeService (Python subprocess, URL → transcript text, error classification)

**Current step:** 5 — TranscriptSanitizerService (`stripBracketNoise` and `normalizeText` done; `formatTimestamp`, snippet pipeline, and `sanitize()` still outstanding)

**Remaining steps:**
- 6 — LlmService (OpenRouter call + structured output: categories + keywords)
- 7 — AnalyzeService (orchestrate URL → youtube → sanitize → llm, or text → sanitize → llm)
- 8 — AnalyzeController (POST /analyze with SSE streaming)
- 9 — AppExceptionFilter (finalize { error: { code, message } } envelope + global registration)

## Why These Tasks
Step 5's three remaining pieces have a strict internal dependency order — `formatTimestamp` must exist before `buildSegments` can call it, and the full pipeline must be wired before `sanitize()` can delegate to it — so the tasks follow that order and each one's completion gate feeds directly into the next.
