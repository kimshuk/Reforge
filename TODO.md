# Daily Tasks — 2026-06-02
## Focus: NestJS Migration — Step 5: TranscriptSanitizerService

## Today's 3 Tasks

- [ ] **Wire up `TranscriptSanitizer.sanitize()` to call its private helpers**
  - The class already has fully implemented `sanitizeSnippetList` and `buildSegments` private helpers — `sanitize()` just needs to accept `RawSnippet[]` (and optionally `SegmentOptions`) as parameters, call them in sequence, and return a `SanitizedTranscript` object
  - `cleanedSnippetCount` must be captured as the length of the array returned by `sanitizeSnippetList` before it is passed into `buildSegments` — this records how many raw snippets survived cleaning, which differs from the number of output segments
  - Done when `sanitize()` no longer throws, returns all three required fields on `SanitizedTranscript`, and `npm run build` inside `backend-nest/` exits with zero TypeScript errors

- [ ] **Add `exports` to `AnalyzeModule` for `TranscriptSanitizer`**
  - NestJS requires an explicit `exports` array in `@Module` for any provider that will be injected outside the module — without it, Step 7's `AnalyzeService` will fail with a cryptic "unknown dependency" DI error at runtime even though the provider is declared
  - The change is a single-line addition to `analyze.module.ts`: an `exports: [TranscriptSanitizer]` entry alongside the existing `providers` array
  - Done when `analyze.module.ts` exports `TranscriptSanitizer` and `npm run build` still passes cleanly

- [ ] **Add `TranscriptSanitizer` class-level tests to the existing spec file**
  - The current spec only tests the three standalone export functions (`stripBracketNoise`, `normalizeText`, `formatTimestamp`); the class itself has zero coverage, meaning any wiring regression would go undetected
  - Add a `describe('TranscriptSanitizer.sanitize')` block that instantiates the class directly (no DI bootstrap needed). Cover: a happy-path call with valid snippets asserting `cleanedSnippetCount`, correct `segmentIndex` shape (`id`/`startSec`/`endSec`/`text`), and `S001 | MM:SS | text` line format in `llmTranscriptText`; an empty-array input; a batch where all snippets are invalid (bad timestamps or noise-only text) expecting `cleanedSnippetCount === 0`; and a single-snippet baseline
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
Step 5 carries over a third day with all three items still unimplemented. These are a strict gate: `AnalyzeService` (Step 7) and `LlmService` (Step 6) both depend on a working, injectable `TranscriptSanitizer`, so nothing downstream can progress until `sanitize()` is wired, the module exports it, and tests confirm the behavior contract.
