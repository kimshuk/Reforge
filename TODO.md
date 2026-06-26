# Daily Tasks — 2026-06-26
## Focus: NestJS Migration — Step 5: TranscriptSanitizerService (class-level tests + module export)

## Today's 3 Tasks

- [ ] **Test `sanitize()` — happy path: noise filtering, merging, and output shape**
  - Instantiate `TranscriptSanitizer` directly (no DI container) and call `sanitize()` with a realistic mix of valid snippets alongside noise entries (`[music]`, `[applause]`) and structurally invalid items (missing or negative `start`); this exercises the full pipeline end-to-end through one public API call
  - Assert that `cleanedSnippetCount` counts only the snippets that survive both the `start`-validity guard and the `normalizeText` non-empty filter, and that it is strictly larger than `segmentIndex.length` — this proves short consecutive snippets are being merged into longer segments rather than emitted one-for-one
  - Assert that every line of `llmTranscriptText` matches the `S001 | MM:SS | text` format exactly — LLM prompt logic parses this structure to extract segment IDs and timestamps, so a malformed line silently corrupts citation lookup during analysis
  - Done when a `describe('TranscriptSanitizer')` block exists in `transcript.sanitizer.spec.ts` and all assertions pass under `npm test` without breaking existing helper-function suites

- [ ] **Test `sanitize()` — edge cases: empty input and fully-invalid batches**
  - Test `sanitize([])`: expect `cleanedSnippetCount: 0`, an empty `sourceSegments` array, an empty `segmentIndex`, and an empty `llmTranscriptText` string — this is the zero-content guard that `AnalyzeService` relies on before attempting LLM calls or persistence
  - Test a batch where every snippet either has an invalid `start` value (negative, `NaN`, non-numeric string) or whose text normalizes to empty after stripping bracket noise: expect `cleanedSnippetCount === 0` and all output fields empty, confirming the sanitizer never surfaces corrupted entries regardless of what the Python subprocess returns
  - Verify the shape of each entry in `sourceSegments`: each must carry `sequence` (zero-based index), `startSec`, `endSec`, `rawText` (original untouched string), and `text` (normalized) — this array is passed directly into `TranscriptStoreService.setTranscript` for per-snippet persistence and is currently untested
  - Done when edge-case assertions pass alongside the Task 1 tests with no regression under `npm test`

- [ ] **Export `TranscriptSanitizer` from `AnalyzeModule` and confirm clean build**
  - Add `exports: [TranscriptSanitizer]` to the `@Module` decorator in `analyze.module.ts` — without this export, any future module that imports `AnalyzeModule` cannot inject `TranscriptSanitizer` even though it is listed as a provider, producing a hard-to-diagnose "unknown provider" runtime error at startup
  - Run `npm run build` inside `backend-nest/` to confirm no TypeScript compilation errors and that the existing module graph (which wires `AnalyzeModule` into `AppModule` alongside `LlmModule`, `TranscriptModule`, and `DatabaseModule`) remains intact
  - Done when `analyze.module.ts` has an `exports` array containing `TranscriptSanitizer` and `npm run build` exits cleanly

## Migration Progress
**Completed steps:**
- 1 — Bootstrap NestJS scaffold (main.ts, app.module.ts, tsconfig strict mode)
- 2 — Project structure (analyze/, common/, all feature modules populated)
- 3 — AppException class (common/app.exception.ts)
- 4 — YoutubeService (Python subprocess, URL → transcript text, error classification)
- 6 — LlmService (multi-provider adapters, topic chunking, candidate clipping, category extraction — implemented ahead of order)
- 7 — AnalyzeService (full pipeline: fetch → sanitize → chunk → clip → store → respond)
- 8 — AnalyzeController (POST /analyze with SSE streaming, non-streaming fallback)
- 9 — AppExceptionFilter (global `{ error: { code, message } }` envelope, registered in main.ts)

**Current step:** 5 — TranscriptSanitizerService (`sanitize()` implemented; class-level tests and module export still outstanding)

**Remaining steps:** None beyond Step 5 — all implementation is complete; finishing these three tasks closes the migration

## Why These Tasks
`TranscriptSanitizer.sanitize()` is on the critical path between raw YouTube snippets and every LLM call, yet has zero class-level test coverage despite helper functions being well-tested. Tasks 1 and 2 close that gap by covering the core merge pipeline and all meaningful edge cases end-to-end; Task 3 is the one-line module export that makes `TranscriptSanitizer` injectable by any future consumer of `AnalyzeModule`.
