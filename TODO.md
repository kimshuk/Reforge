# Daily Tasks — 2026-05-15
## Focus: NestJS Migration — Step 5: TranscriptSanitizerService

## Today's 3 Tasks

- [ ] **Implement and export `formatTimestamp`**
  - Add the `formatTimestamp` function (module-level export, not a class method) that converts a seconds value to `MM:SS`, or `H:MM:SS` for videos over an hour — this exact format is embedded in each segment line that `LlmService` will receive in Step 6, so the output must match the Express backend precisely
  - Handle non-numeric and negative inputs by clamping to zero via `Math.max(0, Math.floor(Number(input) || 0))` — the function must never throw, even if called with `null`, `undefined`, or `NaN`
  - Add focused unit tests covering: sub-hour formatting, super-hour formatting, zero input, negative input, and `NaN` input; all tests passing confirms this piece is ready for `LlmService` to import

- [ ] **Implement the snippet pipeline: flatten, filter, sort, and segment**
  - Port `flattenRawSnippets` (recursively unwraps arbitrarily nested arrays into a flat list of snippet objects) and `sanitizeSnippetList` (rejects snippets with non-finite or negative `start`, normalizes text via `normalizeText`, drops empty-text results, computes `endSec` from `start + duration`, and sorts survivors ascending by `startSec`) — these two together produce the clean, ordered list that `buildSegments` consumes
  - Port `shouldSplitSegment` and `buildSegments` using the threshold constants from the Express backend: a 2.5 s pause triggers an unconditional split; soft caps at 35 s / 320 chars trigger a split only once the segment has matured past 20 s / 180 chars; hard caps at 45 s / 420 chars force a split regardless of maturity — these rules keep segments semantically coherent rather than slicing at arbitrary boundaries
  - `buildSegments` must assign sequential IDs (`S001`, `S002`, …), join each segment's snippets with a single space, and produce an `llmTranscriptText` string formatted as one `"S### | MM:SS | text"` line per segment using the `formatTimestamp` export from the previous task — this exact string is what `AnalyzeService` will pass to `LlmService` in Steps 6–7

- [ ] **Wire `sanitize()` and verify clean build**
  - Replace the `sanitize()` throw-stub with the real implementation: accept a `RawSnippet[]`, run it through `sanitizeSnippetList` then `buildSegments`, and return a fully typed `SanitizedTranscript` (`llmTranscriptText`, `segmentIndex`, `cleanedSnippetCount`) — this is the only public entry point that `AnalyzeService` will call, so its return shape must match the interface exactly
  - Confirm `formatTimestamp` is exported at module level (not scoped inside the class), so `LlmService` can import it as a standalone function without depending on the sanitizer class
  - Run `npm run build` in `backend-nest/` and confirm zero TypeScript errors; run `npm test` to confirm all existing and new tests pass — clean build and green tests are the completion gate for Step 5

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
Step 5 is still the blocking dependency for Steps 6–9: `LlmService` needs `formatTimestamp` to build the prompt, and `AnalyzeService` needs a working `sanitize()` to hand off the transcript. The three tasks are ordered by internal dependency — `formatTimestamp` first because `buildSegments` calls it, then the pipeline that depends on it, then the public method and build verification that seal the Step 5 contract.
