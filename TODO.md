# Daily Tasks — 2026-06-09
## Focus: NestJS Migration — Step 5: TranscriptSanitizerService

## Today's 3 Tasks

- [ ] **Implement `TranscriptSanitizer.sanitize(rawSnippets)`**
  - The two heavy-lifting functions (`sanitizeSnippetList` and `buildSegments`) are already fully implemented in the same file; `sanitize()` just needs to call them in sequence — clean the snippets first, capture how many survived filtering, then build segments from the cleaned list
  - The `cleanedSnippetCount` field must reflect the count after `sanitizeSnippetList` filters out bad-timestamp and noise-only entries, not the number of segments that come out of `buildSegments` — these can differ significantly when many short snippets merge into a single segment
  - Done when `sanitize(rawSnippets)` returns a `SanitizedTranscript` with all three fields populated and `npm run build` inside `backend-nest/` exits cleanly

- [ ] **Export `TranscriptSanitizer` from `AnalyzeModule`**
  - NestJS modules only share their providers with other modules when those providers are listed in an explicit `exports` array — without this, any future service in another module (e.g., `AnalyzeService`) that tries to inject `TranscriptSanitizer` will fail at runtime even though it is declared in `providers`
  - Add `exports: [TranscriptSanitizer]` to `analyze.module.ts` alongside the existing `providers` declaration; no other file needs to change
  - Done when `analyze.module.ts` contains the `exports` field and `npm run build` still passes

- [ ] **Add class-level tests for `TranscriptSanitizer.sanitize()` to the existing spec**
  - The spec currently only exercises the three standalone helper exports (`stripBracketNoise`, `normalizeText`, `formatTimestamp`); the `TranscriptSanitizer` class itself has no test coverage, so a wiring mistake in `sanitize()` would remain invisible
  - Instantiate the class directly (no DI bootstrap needed) and cover at minimum: a happy-path call that verifies `cleanedSnippetCount`, that each `segmentIndex` entry has `id`, `startSec`, `endSec`, and `text`, and that `llmTranscriptText` lines follow the `S001 | MM:SS | text` format; an empty-array input returning zero snippets and an empty string; a batch where every snippet is filtered out (invalid timestamps or noise-only text), expecting `cleanedSnippetCount === 0` and an empty result
  - Done when `npm test` inside `backend-nest/` shows the new `describe` block passing alongside all existing helper tests

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
Step 5 carries over from yesterday with all three tasks still open — `sanitize()` still throws, the module has no exports, and the spec has no class-level coverage — and steps 6 and 7 both depend on `TranscriptSanitizer` being injectable and correct, so these three tasks must close before anything downstream can be built.
