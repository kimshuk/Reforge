# Daily Tasks — 2026-06-15
## Focus: NestJS Migration — Step 5: TranscriptSanitizerService

## Today's 3 Tasks

- [ ] **Implement `TranscriptSanitizer.sanitize()`**
  - The two private helpers `sanitizeSnippetList` and `buildSegments` are fully implemented in the same file — `sanitize()` needs to accept `RawSnippet[]`, call them in sequence, and return the `SanitizedTranscript` shape
  - Capture `cleanedSnippetCount` from the length of the list returned by `sanitizeSnippetList` *before* passing it to `buildSegments`, because segment merging can produce a very different count and the field must reflect the number of clean input snippets, not output segments
  - Done when `sanitize(rawSnippets: RawSnippet[])` returns a `SanitizedTranscript` with all three fields populated and `npm run build` inside `backend-nest/` exits cleanly

- [ ] **Export `TranscriptSanitizer` from `AnalyzeModule`**
  - NestJS only allows cross-module injection for providers listed explicitly in a module's `exports` array — without this, `AnalyzeService` (Step 7) will fail at runtime when it tries to inject `TranscriptSanitizer`, even though the class is declared in `providers`
  - Add `exports: [TranscriptSanitizer]` to the `@Module` decorator in `analyze.module.ts`; no other file needs to change for this task
  - Done when `analyze.module.ts` carries the `exports` field alongside its existing `providers` and `npm run build` still passes

- [ ] **Add class-level tests to the existing `TranscriptSanitizer` spec**
  - The spec currently only covers the three exported helper functions; the `TranscriptSanitizer` class itself is untested, meaning a wiring mistake in `sanitize()` — wrong argument order, wrong field name, missing count — would go undetected
  - Instantiate `TranscriptSanitizer` directly (no NestJS DI bootstrap needed) and cover three cases: a happy-path call with valid snippets verifying that `cleanedSnippetCount` is correct, that each `segmentIndex` entry has `id`/`startSec`/`endSec`/`text`, and that `llmTranscriptText` lines follow the `S001 | MM:SS | text` format; an empty-array input returning zero snippets and an empty `llmTranscriptText`; a batch where every snippet is invalid or noise-only, expecting `cleanedSnippetCount === 0` and empty output
  - Done when `npm test` inside `backend-nest/` shows the new `TranscriptSanitizer` describe block passing alongside all pre-existing helper tests

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
Step 5 carried over with all three tasks still unfinished; `LlmService` and `AnalyzeService` both depend on a working, injectable `TranscriptSanitizer`, so nothing in steps 6–9 can proceed until these are done.
