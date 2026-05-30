# Daily Tasks — 2026-05-30
## Focus: NestJS Migration — Step 5: TranscriptSanitizerService

## Today's 3 Tasks

- [ ] **Implement `TranscriptSanitizer.sanitize()` method body**
  - The class already has `sanitizeSnippetList` and `buildSegments` as module-level functions — the method body just calls them in sequence and returns a `SanitizedTranscript` object with `llmTranscriptText`, `segmentIndex`, and `cleanedSnippetCount`
  - Capture `cleanedSnippetCount` as the length of the cleaned snippet array *after* `sanitizeSnippetList` runs but *before* passing it to `buildSegments` — this number reflects only snippets that survived normalization (valid timestamp + non-empty text), making it a meaningful coverage metric for callers
  - Done when the method no longer throws and `npm run build` inside `backend-nest/` exits with zero TypeScript errors

- [ ] **Export `TranscriptSanitizer` from `AnalyzeModule`**
  - `analyze.module.ts` currently lists `TranscriptSanitizer` in `providers` but omits it from `exports` — NestJS will refuse to inject it into any service outside `AnalyzeModule`, causing a DI bootstrap failure in Step 7 when `AnalyzeService` tries to use it
  - Add `TranscriptSanitizer` to the `exports` array — a one-line change that prevents a cryptic runtime error later; without it, both `LlmService` and `AnalyzeService` will fail to receive the injected instance
  - Done when the module declaration has matching `providers` and `exports` entries for `TranscriptSanitizer` and `npm run build` still exits cleanly

- [ ] **Add `TranscriptSanitizer.sanitize()` unit tests to the existing spec file**
  - The current `transcript.sanitizer.spec.ts` covers only the three exported helper functions; the class method itself has no test — add a `describe('TranscriptSanitizer.sanitize')` block that instantiates the class directly (no NestJS DI bootstrap needed in unit tests)
  - Write at minimum four cases: a happy-path batch of valid snippets (assert `cleanedSnippetCount` equals the number of valid inputs, that `segmentIndex` entries each have all four required fields, and that each line of `llmTranscriptText` matches the `S001 | MM:SS | text` format); an empty-array input; a batch where every snippet has an invalid timestamp or text that normalizes to empty (both should yield `cleanedSnippetCount === 0`); and a single-snippet input to confirm the base case works without segment splitting
  - Done when `npm test` inside `backend-nest/` shows the new describe block passing alongside the pre-existing helper tests

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
Step 5 carries over from yesterday — the `sanitize()` method body, module export, and unit tests are all still unimplemented. Closing these three items is the prerequisite gate for Step 6 (`LlmService`) and Step 7 (`AnalyzeService`), both of which depend on being able to inject and trust `TranscriptSanitizer`.
