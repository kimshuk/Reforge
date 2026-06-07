# Daily Tasks — 2026-06-07
## Focus: NestJS Migration — Step 5: TranscriptSanitizerService

## Today's 3 Tasks

- [ ] **Implement `TranscriptSanitizer.sanitize()`**
  - All the heavy lifting (filtering snippets, merging them into timed segments, formatting the LLM-ready transcript) is already written as module-level helpers; the class method just needs to call them in sequence and return the combined result
  - The method signature should accept `RawSnippet[]` and an optional `SegmentOptions` object — capture the cleaned snippet count from the output of the first helper before passing its result to the second, since that count reflects how many raw snippets survived filtering (not how many segments were produced)
  - Done when `sanitize()` returns a `SanitizedTranscript` with all three fields populated and `npm run build` inside `backend-nest/` exits without errors

- [ ] **Export `TranscriptSanitizer` from `AnalyzeModule`**
  - NestJS only makes a module's providers available to other modules when they appear in an explicit `exports` array — without this, any future service that injects `TranscriptSanitizer` will fail at runtime with a dependency-injection error even though the class is declared in `providers`
  - The fix is a single-line addition to `analyze.module.ts`: add an `exports: [TranscriptSanitizer]` entry alongside the existing `providers` array
  - Done when `analyze.module.ts` has an `exports` field containing `TranscriptSanitizer` and `npm run build` still passes cleanly

- [ ] **Add class-level tests for `TranscriptSanitizer.sanitize()` to the existing spec file**
  - The spec currently only exercises the three standalone helper exports; the `TranscriptSanitizer` class itself is untested, so a wiring mistake in `sanitize()` would go undetected by the test suite
  - Add a `describe('TranscriptSanitizer.sanitize')` block that instantiates the class directly (no DI bootstrap needed) and covers: a happy-path call verifying the correct `cleanedSnippetCount`, that each `segmentIndex` entry has `id`, `startSec`, `endSec`, and `text`, and that `llmTranscriptText` lines follow the `S001 | MM:SS | text` format; an empty-array input returning zero snippets; and a batch where every snippet is filtered (bad timestamps or noise-only text), expecting `cleanedSnippetCount === 0`
  - Done when `npm test` inside `backend-nest/` shows the new describe block passing alongside all existing helper tests

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
Step 5 remains unfinished from yesterday — `sanitize()` still throws `not implemented` and `AnalyzeModule` lacks an `exports` array — so nothing in steps 6 or 7 can be built or tested until these three tasks are closed out.
