# Daily Tasks — 2026-05-14
## Focus: NestJS Migration — Step 5: TranscriptSanitizerService

## Today's 3 Tasks

- [ ] **Implement `normalizeText` and `formatTimestamp` helpers**
  - `normalizeText` takes a raw snippet text string and returns a cleaned version: strip leading `>` quote markers, call `stripBracketNoise`, collapse runs of Korean filler characters (`ㅋ`, `ㅎ`) and repeated punctuation (`!`, `?`, etc.) to at most two, normalize whitespace, and return an empty string for lines made up entirely of decorative symbols — cross-reference `normalizeText` in `backend/src/services/transcriptSanitizer.js` for the exact regex rules
  - `formatTimestamp` converts a seconds value to `MM:SS` (or `H:MM:SS` for videos over an hour); it must safely handle non-numeric and negative inputs by clamping to zero — this function will be imported by `LlmService` in Step 6 to embed timestamps in the prompt, so it must be exported at module level (not just used internally)
  - Add focused unit tests for both functions: non-string input to `normalizeText`, Korean and punctuation collapsing, sub-hour and super-hour timestamp formatting, and NaN/negative clamping; all tests passing is the completion gate

- [ ] **Implement the snippet pipeline: flatten, filter, sort, and segment**
  - Port `flattenRawSnippets` (recursively unwraps nested arrays into a flat list of snippet objects) and `sanitizeSnippetList` (discards snippets with non-finite or negative `start`, normalizes text via `normalizeText`, drops empty-text results, sorts survivors by `startSec`) — these two together produce the clean, ordered list that the segment builder consumes
  - Port `shouldSplitSegment` and `buildSegments` using the threshold constants from the Express backend: pause gap of 2.5 s triggers a split; soft caps at 35 s / 320 chars with a maturity guard at 20 s / 180 chars; hard caps at 45 s / 420 chars — these rules keep segments semantically coherent rather than slicing at arbitrary time boundaries
  - `buildSegments` must assign sequential IDs (`S001`, `S002`, …), join each segment's snippets with a single space, and produce an `llmTranscriptText` string formatted as one `"S### | MM:SS | text"` line per segment — this is the exact string that `LlmService` will receive in Step 6

- [ ] **Wire `sanitize()`, export `formatTimestamp`, and verify clean build**
  - Replace the `sanitize()` throw-stub with the real implementation: accept a raw snippet array, run it through `sanitizeSnippetList` then `buildSegments`, and return a fully typed `SanitizedTranscript` (`llmTranscriptText`, `segmentIndex`, `cleanedSnippetCount`) — this is the only public entry point that `AnalyzeService` will call in Step 7
  - Confirm `formatTimestamp` is exported at the module level (not scoped inside the class), so `LlmService` can import it in Step 6 without depending on the full sanitizer class
  - Run `npm run build` in `backend-nest/` and confirm zero TypeScript errors; run `npm test` to confirm the existing `stripBracketNoise` spec and all new tests pass — clean build and green tests are the completion gate for Step 5

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
Step 5 remains the blocking dependency for all downstream steps — `LlmService` needs `formatTimestamp` to embed timestamps in the prompt, and `AnalyzeService` needs a working `sanitize()` to produce the transcript text it passes to the LLM. The three tasks are ordered by internal dependency: pure helper functions first, then the pipeline that consumes them, then the public `sanitize()` method and `formatTimestamp` export that seal the contract for Steps 6–7.
