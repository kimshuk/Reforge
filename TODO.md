# Daily Tasks — 2026-06-01
## Focus: NestJS Migration — Step 5: TranscriptSanitizerService

## Today's 3 Tasks

- [ ] **Implement `TranscriptSanitizer.sanitize()` method body**
  - The class already contains fully implemented private helpers — `sanitizeSnippetList` (filters and normalizes raw snippets) and `buildSegments` (groups clean snippets into timed segments with LLM-ready text). The public `sanitize()` method just needs to call them in sequence and return a `SanitizedTranscript`
  - Capture `cleanedSnippetCount` as the length of the array returned by `sanitizeSnippetList` *before* passing it into `buildSegments` — this count represents how many raw snippets survived cleaning, which is distinct from how many output segments were produced
  - Done when `sanitize()` no longer throws `not implemented`, returns a `SanitizedTranscript` with all three required fields, and `npm run build` inside `backend-nest/` exits with zero TypeScript errors

- [ ] **Export `TranscriptSanitizer` from `AnalyzeModule`**
  - `analyze.module.ts` declares `TranscriptSanitizer` in `providers` but has no `exports` array — NestJS silently prevents injection across module boundaries without an explicit export, which will cause a cryptic DI failure in Step 7 when `AnalyzeService` tries to consume the sanitizer
  - The fix is a single-line addition: an `exports` array in the `@Module` decorator containing `TranscriptSanitizer`, mirroring the existing `providers` entry
  - Done when `analyze.module.ts` has a matching `exports` entry for `TranscriptSanitizer` and `npm run build` still exits cleanly

- [ ] **Add `TranscriptSanitizer.sanitize()` unit tests to the existing spec file**
  - The existing spec covers only the three standalone export functions — the class itself has zero test coverage, meaning any regression in the `sanitize()` wiring would go undetected
  - Add a `describe('TranscriptSanitizer.sanitize')` block that instantiates the class directly (no NestJS DI bootstrapping needed for unit tests). Cover at minimum: a happy-path batch asserting `cleanedSnippetCount` equals the number of valid input snippets, that `segmentIndex` entries contain `id`/`startSec`/`endSec`/`text`, and that each `llmTranscriptText` line follows the `S001 | MM:SS | text` format; an empty-array input; a batch where all snippets are invalid (bad timestamps or noise-only text), expecting `cleanedSnippetCount === 0`; and a single-snippet input to confirm the base case works
  - Done when `npm test` inside `backend-nest/` shows the new describe block passing alongside all pre-existing helper tests

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
All three Step 5 items carry over from 2026-05-31 with zero progress — the `sanitize()` method still throws, the module export is missing, and the spec file has no class-level coverage. These three tasks are the prerequisite gate before Step 6 (LlmService) and Step 7 (AnalyzeService) can begin, since both will inject and depend on a working `TranscriptSanitizer`.
