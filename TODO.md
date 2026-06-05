# Daily Tasks — 2026-06-05
## Focus: NestJS Migration — Step 5: TranscriptSanitizerService

## Today's 3 Tasks

- [ ] **Implement `TranscriptSanitizer.sanitize()`**
  - The class body currently throws `not implemented`; the two module-level helpers (`sanitizeSnippetList`, `buildSegments`) are fully written and just need to be called in sequence from `sanitize()`
  - The method signature must accept `RawSnippet[]` as its first argument and an optional `SegmentOptions` object as a second; `cleanedSnippetCount` should be captured as the length of the cleaned array before it is passed to `buildSegments`, since that count reflects how many raw snippets survived the cleaning step — not how many output segments were produced
  - Done when `sanitize()` returns a `SanitizedTranscript` with all three fields (`llmTranscriptText`, `segmentIndex`, `cleanedSnippetCount`) and `npm run build` inside `backend-nest/` exits cleanly

- [ ] **Export `TranscriptSanitizer` from `AnalyzeModule`**
  - NestJS does not make a module's providers available outside the module unless they are listed in an `exports` array — without this, `AnalyzeService` (Step 7) will fail at runtime with a dependency injection error even though the provider is declared in `providers`
  - The change is a single-line addition to `analyze.module.ts`: an `exports: [TranscriptSanitizer]` entry alongside the existing `providers` array
  - Done when `analyze.module.ts` has an `exports` field containing `TranscriptSanitizer` and `npm run build` still passes

- [ ] **Add class-level tests for `TranscriptSanitizer.sanitize()` to the existing spec file**
  - The spec currently only covers the three standalone helper exports; the class itself is untested, meaning a wiring regression in `sanitize()` would go undetected
  - Add a `describe('TranscriptSanitizer.sanitize')` block that instantiates the class directly (no DI bootstrap needed) and covers: a happy-path call asserting the correct `cleanedSnippetCount`, the shape of each `segmentIndex` entry (`id`, `startSec`, `endSec`, `text`), and that `llmTranscriptText` lines follow the `S001 | MM:SS | text` format; an empty-array input; and a batch where every snippet is filtered out (bad timestamps or noise-only text), expecting `cleanedSnippetCount === 0`
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
All three Step 5 tasks carried over from 2026-06-04 with no progress; `sanitize()` must be implemented and exported before `LlmService` and `AnalyzeService` (steps 6–7) can be built or meaningfully tested, so nothing downstream can advance until this step is closed out.
