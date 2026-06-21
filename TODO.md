# Daily Tasks — 2026-06-21
## Focus: NestJS Migration — Step 5: TranscriptSanitizerService (carried over)

## Today's 3 Tasks

- [ ] **Add `TranscriptSanitizer` class-level tests — core pipeline behavior**
  - Instantiate `TranscriptSanitizer` directly (no DI container needed) and call `sanitize()` with a realistic mix of valid snippets, noise-bracket entries (`[music]`, `[applause]`), and structurally invalid items (missing or negative `start`) — this exercises the full `sanitizeSnippetList → buildSegments` path in a single test
  - Assert that `cleanedSnippetCount` equals the number of snippets that survive both the `start`-validity filter and the `normalizeText` empty-text filter; this count is a pre-merge tally and should be larger than the number of entries in `segmentIndex`, confirming that short consecutive snippets are merged into longer segments
  - Assert that every line in `llmTranscriptText` matches the `S001 | MM:SS | text` format exactly — all downstream LLM prompts parse this format to extract segment IDs and timestamps, so a single malformed line silently corrupts citation lookup in the LLM pipeline
  - Done when a `describe('TranscriptSanitizer')` block appears in `transcript.sanitizer.spec.ts` and all tests (existing helper tests plus the new block) pass under `npm test`

- [ ] **Add `TranscriptSanitizer` class-level tests — edge cases and `sourceSegments`**
  - Test `sanitize([])`: must return `cleanedSnippetCount: 0`, an empty `sourceSegments` array, an empty `segmentIndex`, and an empty `llmTranscriptText` string — this is the zero-content guard that both `AnalyzeService` and `TranscriptStoreService` rely on before attempting persistence or LLM calls
  - Test a batch where every snippet either has an invalid `start` value (negative, `NaN`, non-numeric) or normalizes to empty text after `stripBracketNoise` / `normalizeText`: expect `cleanedSnippetCount === 0` and all four output fields empty, confirming the sanitizer never surfaces corrupted entries regardless of what the Python subprocess returns
  - Test the `sourceSegments` array specifically: each entry must carry the correct `sequence` index (zero-based position in the post-filter snippet list), `startSec`, `endSec`, `rawText` (the original untouched string), and `text` (the normalized version) — `sourceSegments` is passed directly into `TranscriptStoreService.setTranscript` for per-snippet database persistence and is entirely untested today
  - Done when all edge-case assertions pass alongside the Task 1 tests without any regression in the existing `stripBracketNoise`, `normalizeText`, or `formatTimestamp` helper suites

- [ ] **Export `TranscriptSanitizer` from `AnalyzeModule` and confirm clean build**
  - Add an `exports: [TranscriptSanitizer]` array to the `@Module` decorator in `analyze.module.ts` — without this export, any future module that imports `AnalyzeModule` cannot inject `TranscriptSanitizer` even though it is listed as a provider, causing a hard-to-diagnose runtime "unknown provider" error at startup
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

**Current step:** 5 — TranscriptSanitizerService (`sanitize()` implemented; class-level tests and module export still outstanding)

**Remaining steps:** None — all implementation complete; only step 5 quality tasks remain before the migration can be called done

## Why These Tasks
Step 5 is the only incomplete step in the migration: `TranscriptSanitizer.sanitize()` sits on the critical path from raw YouTube snippets to every LLM call, yet has zero class-level test coverage. Tasks 1 and 2 close that gap by testing the core pipeline and all meaningful edge cases; Task 3 is a one-line module export that makes `TranscriptSanitizer` injectable by any future consumer of `AnalyzeModule`.
