# Daily Tasks — 2026-05-29
## Focus: NestJS Migration — Step 5: TranscriptSanitizerService

## Today's 3 Tasks

- [ ] **Implement `TranscriptSanitizer.sanitize()` method body**
  - The class already has all the private helper functions it needs (`sanitizeSnippetList`, `buildSegments`); the method just needs to call them in sequence and return a properly typed `SanitizedTranscript` object
  - Capture the cleaned snippet count *before* passing the array to `buildSegments` — this count must reflect only snippets that survived normalization (valid timestamp + non-empty text), not the raw input length, so downstream services can use it as a meaningful coverage metric
  - The correct signature is `sanitize(rawSnippets: RawSnippet[], options?: SegmentOptions): SanitizedTranscript` — all these types are already exported from the same file, so no new imports are needed
  - Done when the method no longer throws and `npm run build` exits with zero TypeScript errors inside `backend-nest/`

- [ ] **Export `TranscriptSanitizer` from `AnalyzeModule`**
  - `analyze.module.ts` currently lists `TranscriptSanitizer` in `providers` but not in `exports` — this means NestJS will refuse to inject it into any service that lives outside of `AnalyzeModule`, which will cause a DI bootstrap failure in Step 7 when `AnalyzeService` tries to use it
  - Add `TranscriptSanitizer` to the `exports` array alongside its `providers` entry — a one-line change, but skipping it now means a cryptic runtime error later
  - Done when the module declaration has both `providers` and `exports` entries for `TranscriptSanitizer` and `npm run build` still exits cleanly

- [ ] **Add `TranscriptSanitizer.sanitize()` unit tests to the existing spec file**
  - The current `transcript.sanitizer.spec.ts` only covers the three exported helpers; the class method itself has no test coverage — add a `describe('TranscriptSanitizer.sanitize')` block that instantiates the class directly (no NestJS DI bootstrap needed in unit tests)
  - Write at minimum four cases: a happy-path batch of valid snippets (assert `cleanedSnippetCount` equals the number of valid inputs, that each `segmentIndex` entry has all four required fields, and that each line of `llmTranscriptText` matches the `S001 | MM:SS | text` format); an empty-array input; a batch where every snippet has an invalid timestamp or text that normalizes to empty (both empty-array and all-invalid should yield `cleanedSnippetCount === 0`); and a single-snippet input to confirm the base case works without segment splitting
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
All the segmentation logic already exists as module-level functions — closing Step 5 is a small, self-contained method body plus the module export fix and test coverage that prevent silent failures from propagating into Steps 6 and 7. Getting the DI wiring right now means `LlmService` and `AnalyzeService` can inject `TranscriptSanitizer` without surprises.
