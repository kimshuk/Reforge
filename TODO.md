# Daily Tasks — 2026-06-22
## Focus: NestJS Migration — Step 5: TranscriptSanitizerService (carried over)

## Today's 3 Tasks

- [ ] **Test `TranscriptSanitizer.sanitize()` — happy path and segment format**
  - Instantiate `TranscriptSanitizer` directly (no DI container) and call `sanitize()` with a realistic mix of valid snippets, noise-bracket entries (`[music]`, `[applause]`), and structurally invalid items (missing or negative `start`) — this exercises the full `sanitizeSnippetList → buildSegments` path in one test
  - Assert that `cleanedSnippetCount` equals only the snippets that pass both the `start`-validity filter and the `normalizeText` non-empty filter; confirm it is larger than `segmentIndex.length`, proving that short consecutive snippets are being merged into longer segments as intended
  - Assert that every line in `llmTranscriptText` matches `S001 | MM:SS | text` exactly — downstream LLM prompts parse this format to extract segment IDs and timestamps, so a single malformed line silently corrupts citation lookup
  - Done when a `describe('TranscriptSanitizer')` block appears in `transcript.sanitizer.spec.ts` and all tests pass under `npm test`

- [ ] **Test `TranscriptSanitizer.sanitize()` — edge cases and `sourceSegments` shape**
  - Test `sanitize([])`: expect `cleanedSnippetCount: 0`, an empty `sourceSegments` array, an empty `segmentIndex`, and an empty `llmTranscriptText` string — this is the zero-content guard that `AnalyzeService` relies on before attempting LLM calls or persistence
  - Test a batch where every snippet either has an invalid `start` value (negative, `NaN`, non-numeric string) or normalizes to empty text after `stripBracketNoise` / `normalizeText`: expect `cleanedSnippetCount === 0` and all four output fields empty, confirming the sanitizer never surfaces corrupted entries regardless of what the Python subprocess returns
  - Verify the `sourceSegments` array shape: each entry must carry the correct zero-based `sequence` index, `startSec`, `endSec`, `rawText` (original untouched string), and `text` (normalized) — this array is passed directly into `TranscriptStoreService.setTranscript` for per-snippet database persistence and is currently untested
  - Done when all edge-case assertions pass alongside the Task 1 tests with no regression in the existing helper suites

- [ ] **Export `TranscriptSanitizer` from `AnalyzeModule` and confirm clean build**
  - Add an `exports: [TranscriptSanitizer]` entry to the `@Module` decorator in `analyze.module.ts` — without it, any future module importing `AnalyzeModule` cannot inject `TranscriptSanitizer` even though it is listed as a provider, causing a hard-to-diagnose "unknown provider" runtime error at startup
  - Run `npm run build` inside `backend-nest/` to confirm no TypeScript compilation errors are introduced and that the existing module graph (which already wires `AnalyzeModule` into `AppModule` alongside `LlmModule`, `TranscriptModule`, and `DatabaseModule`) remains intact
  - Done when `analyze.module.ts` has an `exports` array containing `TranscriptSanitizer` and `npm run build` exits cleanly with no errors

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

**Current step:** 5 — TranscriptSanitizerService (`sanitize()` implemented; class-level tests and module export outstanding)

**Remaining steps:** None — all implementation complete; only step 5 quality tasks remain before the migration is done

## Why These Tasks
`TranscriptSanitizer.sanitize()` sits on the critical path between raw YouTube snippets and every LLM call, yet has zero class-level test coverage. Tasks 1 and 2 close that gap by testing the core pipeline and all meaningful edge cases; Task 3 is the one-line module export that makes `TranscriptSanitizer` injectable by any future consumer of `AnalyzeModule`.
