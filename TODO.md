# Daily Tasks — 2026-05-18
## Focus: NestJS Migration — Step 5: TranscriptSanitizerService

## Today's 3 Tasks

- [ ] **Fix `normalizeText` divergence and implement `formatTimestamp`**
  - The current `normalizeText` implementation silently diverges from the Express reference: it deletes Korean laugh/hype runs (`ㅋ{3,}`, `ㅎ{3,}`) entirely rather than collapsing them to double characters (`ㅋㅋ`, `ㅎㅎ`). Fix this now before the pipeline is wired, so the bug doesn't propagate silently into LLM input.
  - Implement `formatTimestamp` as a module-level export (not enclosed in the class): convert raw seconds to `MM:SS` for videos under an hour, or `H:MM:SS` for videos at or beyond 3600 s. The exact string it produces is embedded in every segment line sent to the LLM, so it must match the Express backend exactly.
  - Add or extend unit tests to cover `formatTimestamp` (sub-hour, super-hour, zero, non-numeric input) and the corrected Korean-collapsing behavior in `normalizeText` — all tests green is the completion gate for this task.

- [ ] **Implement the snippet pipeline: flatten, filter, sort, and segment**
  - Implement `flattenRawSnippets` (recursively collapses arbitrarily nested arrays into a flat list of snippet objects) and `sanitizeSnippetList` (rejects snippets with non-finite or negative `start`, normalizes each snippet's text through `normalizeText`, drops results with empty text, computes `endSec` as `start + duration`, and sorts survivors ascending by `startSec`) — these two produce the clean ordered list that `buildSegments` consumes.
  - Implement `shouldSplitSegment` and `buildSegments` using the same threshold constants as the Express backend: a pause greater than 2.5 s triggers an unconditional split; soft caps at 35 s / 320 chars trigger a split only when the segment has matured past 20 s / 180 chars; hard caps at 45 s / 420 chars force a split regardless of maturity.
  - `buildSegments` must produce sequential `S001`/`S002`/… IDs, join each segment's parts with a single space, and format `llmTranscriptText` as one `"S### | MM:SS | text"` line per segment using `formatTimestamp` — this exact string format is what `AnalyzeService` will pass to `LlmService` in Step 6.

- [ ] **Wire `sanitize()` and verify clean build**
  - Replace the `sanitize()` throw-stub with a real implementation: accept `RawSnippet[]`, run it through `sanitizeSnippetList` then `buildSegments`, and return a `SanitizedTranscript` (`llmTranscriptText`, `segmentIndex`, `cleanedSnippetCount`) — this is the only public method `AnalyzeService` will call, so its return shape must match the interface already defined in the file.
  - Confirm `formatTimestamp` remains exported at module level (not enclosed inside the class), since `LlmService` will import it directly as a standalone utility in Step 6.
  - Run `npm run build` in `backend-nest/` and confirm zero TypeScript errors; run `npm test` to confirm all existing and new tests pass — a clean build and green tests are the completion gate for Step 5 and unlock Step 6 (LlmService).

## Migration Progress
**Completed steps:**
- 1 — Bootstrap NestJS scaffold (health module, main.ts, tsconfig strict mode)
- 2 — Project structure (analyze/ and common/ stubs, AnalyzeModule wired into AppModule)
- 3 — AppException class (common/app.exception.ts)
- 4 — YoutubeService (Python subprocess, URL → transcript text, error classification)

**Current step:** 5 — TranscriptSanitizerService (`stripBracketNoise` and `normalizeText` scaffolded; `normalizeText` has a Korean-char divergence bug; `formatTimestamp`, snippet pipeline, and `sanitize()` all still outstanding)

**Remaining steps:**
- 6 — LlmService (OpenRouter call + structured output: categories + keywords)
- 7 — AnalyzeService (orchestrate URL → youtube → sanitize → llm, or text → sanitize → llm)
- 8 — AnalyzeController (POST /analyze with SSE streaming)
- 9 — AppExceptionFilter (finalize { error: { code, message } } envelope + global registration)

## Why These Tasks
Task 1 fixes a pre-existing behavioral bug and establishes `formatTimestamp`, which Task 2 depends on directly inside `buildSegments`. Task 3 then wires the completed pipeline through the public `sanitize()` method and gates the whole step with a clean build, ensuring nothing moves forward on a broken foundation.
