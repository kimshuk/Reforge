# Daily Tasks — 2026-06-16
## Focus: NestJS Migration — Step 5: TranscriptSanitizerService (close-out)

## Today's 3 Tasks

- [ ] **Add `TranscriptSanitizer` class-level tests — core behavior**
  - Instantiate `TranscriptSanitizer` directly (no DI needed) and call `sanitize()` with a realistic mix of valid, noisy, and invalid snippets to exercise the full `sanitizeSnippetList → buildSegments` pipeline in one shot
  - Assert `cleanedSnippetCount` matches the number of snippets that survived normalization — not the number of output segments, because the sanitizer merges clean snippets into larger segments and the count must reflect the pre-merge input
  - Assert every entry in `llmTranscriptText` follows the `S001 | MM:SS | text` format that every downstream LLM prompt relies on for segment-grounded citations
  - Done when a new `describe('TranscriptSanitizer')` block appears in `transcript.sanitizer.spec.ts` and all existing plus new tests pass under `npm test`

- [ ] **Add `TranscriptSanitizer` class-level tests — edge cases and `sourceSegments`**
  - Test empty array input: `sanitize([])` must return `cleanedSnippetCount: 0` and empty `segmentIndex`, `llmTranscriptText`, and `sourceSegments` — this is the zero-content guard that both the pipeline and store rely on
  - Test a batch where every snippet either carries an invalid `start` value or normalizes to empty text, expecting `cleanedSnippetCount === 0` and all output arrays empty, confirming the sanitizer never surfaces bad entries to the LLM
  - Test the `sourceSegments` field specifically: verify each entry carries correct `sequence`, `startSec`, `endSec`, `rawText`, and `text` values — this field feeds directly into `TranscriptStoreService.setTranscript` for per-snippet persistence and is entirely untested today
  - Done when these edge cases pass alongside the Task 1 tests without any regression in the existing helper-function tests

- [ ] **Export `TranscriptSanitizer` from `AnalyzeModule` and confirm build is clean**
  - Add `exports: [TranscriptSanitizer]` to the `@Module` decorator in `analyze.module.ts` — without this, any future module that imports `AnalyzeModule` cannot inject `TranscriptSanitizer`, even though it is declared in `providers`; making it exportable now is a cheap correctness guarantee that prevents a hard-to-debug injection error later
  - Run `npm run build` inside `backend-nest/` to confirm that exposing the export does not disturb the TypeScript compilation or the module dependency graph, which already wires `AnalyzeModule` into `AppModule`
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
Steps 6–9 were implemented ahead of order in the `feat: add durable Nest analysis pipeline` commit, so step 5 is the sole blocker to declaring the migration complete; closing out its two remaining tasks (tests + export) is the minimum work needed to move from "code exists" to "step verified and finished."
