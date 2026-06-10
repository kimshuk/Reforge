# Daily Tasks — 2026-06-10
## Focus: NestJS Migration — Step 5: TranscriptSanitizerService

## Today's 3 Tasks

- [ ] **Implement `TranscriptSanitizer.sanitize(rawSnippets)`**
  - The method body should call `sanitizeSnippetList` then `buildSegments` in sequence — both helpers are already implemented in the same file and are ready to use
  - `cleanedSnippetCount` must be captured from the output of `sanitizeSnippetList` before passing those snippets to `buildSegments`, because the segment count after merging can differ significantly from the snippet count after filtering
  - Done when `sanitize(rawSnippets: RawSnippet[])` returns a `SanitizedTranscript` with all three fields populated and `npm run build` inside `backend-nest/` exits with code 0

- [ ] **Export `TranscriptSanitizer` from `AnalyzeModule`**
  - NestJS modules gate cross-module injection through an explicit `exports` array — without it, any service in another module that injects `TranscriptSanitizer` will fail at runtime even though it appears in `providers`
  - Add `exports: [TranscriptSanitizer]` to the `@Module` decorator in `analyze.module.ts`; no other file needs to change for this task
  - Done when `analyze.module.ts` contains the `exports` field alongside its existing `providers` and `npm run build` still passes

- [ ] **Add class-level tests for `TranscriptSanitizer` to the existing spec**
  - The spec currently covers only the three exported helper functions; the `TranscriptSanitizer` class itself is untested, meaning a wiring mistake in `sanitize()` would not be caught
  - Instantiate `TranscriptSanitizer` directly (no DI bootstrap needed) and cover: a happy-path call verifying `cleanedSnippetCount`, that each entry in `segmentIndex` has `id`, `startSec`, `endSec`, and `text`, and that lines in `llmTranscriptText` follow the `S001 | MM:SS | text` format; an empty-array input returning zero snippets and an empty `llmTranscriptText`; a batch where every snippet is filtered (invalid timestamps or noise-only text), expecting `cleanedSnippetCount === 0`
  - Done when `npm test` inside `backend-nest/` shows the new `describe` block passing alongside all pre-existing helper tests

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
Step 5 carries over with all three tasks still open — `sanitize()` still throws, the module has no exports array, and the spec has no class-level coverage. Steps 6 and 7 both depend on `TranscriptSanitizer` being injectable and correct, so all three tasks must close before anything downstream can be wired up.
