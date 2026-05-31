# Daily Tasks — 2026-05-31
## Focus: NestJS Migration — Step 5: TranscriptSanitizerService

## Today's 3 Tasks

- [ ] **Implement `TranscriptSanitizer.sanitize()` method body**
  - The private helper functions `sanitizeSnippetList` and `buildSegments` are already fully implemented in the same file — the `sanitize()` method just needs to call them in sequence, capture the count of cleaned snippets between the two steps, and return a `SanitizedTranscript` with `llmTranscriptText`, `segmentIndex`, and `cleanedSnippetCount`
  - `cleanedSnippetCount` must reflect the number of snippets that survived `sanitizeSnippetList` (i.e. had a valid timestamp and non-empty normalized text) — captured before passing the list into `buildSegments`, so it represents input coverage rather than output segment count
  - Done when the method no longer throws `not implemented` and `npm run build` inside `backend-nest/` exits with zero TypeScript errors

- [ ] **Export `TranscriptSanitizer` from `AnalyzeModule`**
  - `analyze.module.ts` lists `TranscriptSanitizer` in `providers` but has no `exports` array — NestJS will silently refuse to inject it into any service outside `AnalyzeModule`, causing a cryptic DI bootstrap failure in Step 7 when `AnalyzeService` tries to consume it
  - The fix is a one-line addition: add an `exports` array containing `TranscriptSanitizer` to the `@Module` decorator, matching what's already in `providers`
  - Done when `analyze.module.ts` has matching `providers` and `exports` entries for `TranscriptSanitizer` and `npm run build` still exits cleanly

- [ ] **Add `TranscriptSanitizer.sanitize()` unit tests to the existing spec file**
  - The existing `transcript.sanitizer.spec.ts` covers only the three standalone helper functions — the class itself has zero test coverage; add a `describe('TranscriptSanitizer.sanitize')` block that instantiates the class directly (no NestJS DI needed for unit tests)
  - Write at minimum four cases: a happy-path batch of valid snippets asserting that `cleanedSnippetCount` equals the number of valid inputs, that `segmentIndex` entries contain the required `id`/`startSec`/`endSec`/`text` fields, and that each line of `llmTranscriptText` follows the `S001 | MM:SS | text` format; an empty-array input; a batch where every snippet has an invalid timestamp or text that normalizes to empty (both should yield `cleanedSnippetCount === 0`); and a single-snippet input to confirm the base case works without segment splitting
  - Done when `npm test` inside `backend-nest/` shows the new describe block passing alongside the pre-existing helper function tests

## Migration Progress
**Completed steps:**
- 1 — Bootstrap NestJS scaffold (main.ts, app.module.ts, tsconfig strict mode)
- 2 — Project structure (analyze/ and common/ stubs, AnalyzeModule wired into AppModule)
- 3 — AppException class (common/app.exception.ts)
- 4 — YoutubeService (Python subprocess, URL → transcript text, error classification)

**Current step:** 5 — TranscriptSanitizerService (`sanitize()` method, module export, unit tests)

**Remaining steps:**
- 6 — LlmService (OpenRouter call + structured output)
- 7 — AnalyzeService (orchestrate URL → youtube → sanitize → llm, or text → sanitize → llm)
- 8 — AnalyzeController (POST /analyze with SSE streaming)
- 9 — AppExceptionFilter (finalize `{ error: { code, message } }` envelope + global registration)

## Why These Tasks
All three Step 5 items carry over from yesterday — none were implemented. Closing them is the prerequisite gate for Step 6 (`LlmService`) and Step 7 (`AnalyzeService`), both of which depend on being able to inject and trust a working `TranscriptSanitizer`.
