# Daily Tasks — 2026-06-08
## Focus: NestJS Migration — Step 5: TranscriptSanitizerService

## Today's 3 Tasks

- [ ] **Implement `TranscriptSanitizer.sanitize()`**
  - The helper functions (`sanitizeSnippetList`, `buildSegments`) are fully implemented as module-level functions; `sanitize()` just needs to call them in sequence, capture the cleaned snippet count from the first helper's output, and return a `SanitizedTranscript` with all three fields populated (`llmTranscriptText`, `segmentIndex`, `cleanedSnippetCount`)
  - The `cleanedSnippetCount` must be taken from the intermediate cleaned snippet array (after filtering) rather than from the final segment count — these two numbers differ whenever multiple snippets merge into one segment
  - Done when calling `sanitize(rawSnippets)` returns a valid `SanitizedTranscript` and `npm run build` inside `backend-nest/` exits cleanly

- [ ] **Export `TranscriptSanitizer` from `AnalyzeModule`**
  - NestJS dependency injection only makes a module's providers available outside that module when they appear in an explicit `exports` array — without this, any service in another module that injects `TranscriptSanitizer` will fail at runtime even though it is declared in `providers`
  - Add `exports: [TranscriptSanitizer]` to `analyze.module.ts` alongside the existing `providers` array — this is the only change needed
  - Done when `analyze.module.ts` contains an `exports` field with `TranscriptSanitizer` and `npm run build` still passes

- [ ] **Add class-level tests for `TranscriptSanitizer.sanitize()` to the existing spec**
  - The spec currently only exercises the three standalone helper exports; the `TranscriptSanitizer` class is untested, so a wiring mistake in `sanitize()` would go undetected
  - Add a `describe('TranscriptSanitizer.sanitize')` block that instantiates the class directly (no DI bootstrap needed) and covers: a happy-path call verifying `cleanedSnippetCount`, that each `segmentIndex` entry has `id`, `startSec`, `endSec`, and `text`, and that `llmTranscriptText` lines follow the `S001 | MM:SS | text` format; an empty-array input returning zero snippets and an empty string; and a batch where every snippet is filtered (bad timestamps or noise-only text), expecting `cleanedSnippetCount === 0` and an empty result
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
Step 5 carried over from yesterday with all three tasks still open — `sanitize()` still throws, the module exports no providers, and the spec has no class-level coverage — so nothing in steps 6 or 7 can be built or injected correctly until these three tasks are closed out first.
