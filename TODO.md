# Daily Tasks — 2026-06-19
## Focus: NestJS Migration — Step 5: TranscriptSanitizerService (close-out, carried over)

## Today's 3 Tasks

- [ ] **Add `TranscriptSanitizer` class-level tests — core behavior**
  - Instantiate `TranscriptSanitizer` directly (no DI needed) and call `sanitize()` with a realistic mix of valid, noisy, and structurally invalid snippets so the full `sanitizeSnippetList → buildSegments` pipeline runs end-to-end in one test
  - Assert that `cleanedSnippetCount` equals the number of snippets that survived normalization — this is a pre-merge count, so it should be larger than the number of output segments produced by `buildSegments`
  - Assert that every line in `llmTranscriptText` matches the `S001 | MM:SS | text` format that all downstream LLM prompts rely on for segment-grounded citations; a single malformed line would silently corrupt citation lookup
  - Done when a new `describe('TranscriptSanitizer')` block appears in `transcript.sanitizer.spec.ts` and all tests (existing helper tests plus the new block) pass under `npm test`

- [ ] **Add `TranscriptSanitizer` class-level tests — edge cases and `sourceSegments`**
  - Test `sanitize([])`: must return `cleanedSnippetCount: 0` and empty `segmentIndex`, `llmTranscriptText`, and `sourceSegments` arrays — this is the zero-content guard that both the pipeline and `TranscriptStoreService` depend on before attempting persistence
  - Test a batch where every snippet has an invalid `start` value or normalizes to empty text: expect `cleanedSnippetCount === 0` and all outputs empty, confirming the sanitizer never surfaces bad entries to the LLM regardless of what the Python subprocess returns
  - Test `sourceSegments` values specifically: verify each entry carries the correct `sequence` index, `startSec`, `endSec`, `rawText`, and `text` — this is the field passed directly into `TranscriptStoreService.setTranscript` for per-snippet persistence and is entirely untested today
  - Done when all edge-case assertions pass alongside the Task 1 tests without any regression in the existing `stripBracketNoise`, `normalizeText`, or `formatTimestamp` suites

- [ ] **Export `TranscriptSanitizer` from `AnalyzeModule` and confirm build is clean**
  - Add `exports: [TranscriptSanitizer]` to the `@Module` decorator in `analyze.module.ts` — without this, any future module that imports `AnalyzeModule` cannot inject `TranscriptSanitizer` even though it is declared in `providers`, which produces a hard-to-diagnose runtime injection error
  - Run `npm run build` inside `backend-nest/` to confirm that adding the export does not introduce any TypeScript compilation errors or disturb the module dependency graph that already wires `AnalyzeModule` into `AppModule`
  - Done when `analyze.module.ts` has an `exports` array containing `TranscriptSanitizer` and the build exits with no errors

## Migration Progress
**Completed steps:**
- 1 — Bootstrap NestJS scaffold (main.ts, app.module.ts, tsconfig strict mode)
- 2 — Project structure (analyze/, common/, all feature modules populated)
- 3 — AppException class (common/app.exception.ts)
- 4 — YoutubeService (Python subprocess, URL → transcript text, error classification)
- 6 — LlmService (multi-provider adapters, topic chunking, candidate clipping, category extraction, summary — implemented ahead of order)
- 7 — AnalyzeService (full pipeline: fetch → sanitize → chunk → clip → store → respond)
- 8 — AnalyzeController (POST /analyze with SSE streaming, non-streaming fallback)
- 9 — AppExceptionFilter (global `{ error: { code, message } }` envelope, registered in main.ts)

**Current step:** 5 — TranscriptSanitizerService (`sanitize()` implemented; class-level tests and module export still outstanding)

**Remaining steps:** None — all implementation complete; only step 5 quality tasks remain before the migration can be called done

## Why These Tasks
These three tasks have been carried over since 2026-06-16 without being started; they are the only remaining gate before the full NestJS migration can be marked complete. Tasks 1 and 2 cover the entirely untested `sanitize()` surface in `transcript.sanitizer.spec.ts`, and Task 3 is a one-line module change that ensures `TranscriptSanitizer` is injectable by any future consumer of `AnalyzeModule`.
