# Daily Tasks — 2026-06-27
## Focus: NestJS Migration — Step 5: TranscriptSanitizerService (class-level tests + module export)

## Today's 3 Tasks

- [ ] **Test `sanitize()` — happy path: noise filtering, merging, and output shape**
  - Call `sanitize()` on a representative batch of snippets that includes legitimate speech, noise-only entries (`[music]`, `[applause]`), and structurally invalid items (negative or non-numeric `start`); this exercises the full internal pipeline — flatten → filter → merge → format — through the single public method the rest of the app calls
  - Verify that `cleanedSnippetCount` reflects only the snippets that survived both the `start`-validity guard and the `normalizeText` non-empty check, and that `segmentIndex.length` is smaller than `cleanedSnippetCount` — the gap confirms that short consecutive snippets are actually being merged rather than emitted one-for-one
  - Check that every line of `llmTranscriptText` follows the exact `S001 | MM:SS | text` pattern — downstream LLM prompts parse this structure to recover segment IDs and timestamps for citation, so a malformed line silently corrupts the analysis step
  - Done when a `describe('TranscriptSanitizer')` block is present in `transcript.sanitizer.spec.ts` and all assertions pass under `npm test` alongside the existing helper-function suites

- [ ] **Test `sanitize()` — edge cases: empty input and fully-invalid batches**
  - Call `sanitize([])` and assert `cleanedSnippetCount: 0`, `sourceSegments: []`, `segmentIndex: []`, and `llmTranscriptText: ''` — `AnalyzeService` relies on this zero-content path to skip LLM calls and persistence rather than sending an empty prompt
  - Pass a batch where every item either has an invalid `start` (negative, `NaN`, non-numeric string) or normalizes to empty text after noise stripping; expect all four output fields to be empty, confirming no corrupted entries ever reach the LLM regardless of what the Python subprocess returns
  - Assert the shape of each entry in `sourceSegments`: must carry `sequence` (zero-based), `startSec`, `endSec`, `rawText` (original, untouched), and `text` (normalized) — this array flows directly into `TranscriptStoreService.setTranscript` for per-snippet persistence and currently has no test coverage verifying its field contract
  - Done when edge-case assertions pass alongside the Task 1 suite with no regression under `npm test`

- [ ] **Export `TranscriptSanitizer` from `AnalyzeModule` and confirm clean build**
  - Add `exports: [TranscriptSanitizer]` to the `@Module` decorator in `analyze.module.ts` — without this, any future module that imports `AnalyzeModule` will fail at startup with an opaque "unknown provider" error even though `TranscriptSanitizer` is listed as a provider
  - Run `npm run build` inside `backend-nest/` to verify that no TypeScript compilation errors are introduced and that the existing module graph — `AnalyzeModule` wired into `AppModule` alongside `LlmModule`, `TranscriptModule`, and `DatabaseModule` — remains intact
  - Done when `analyze.module.ts` has an `exports` array containing `TranscriptSanitizer` and `npm run build` exits with status 0

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
`TranscriptSanitizer.sanitize()` is the critical gateway between raw Python subprocess output and every LLM call in the pipeline, yet the only existing tests cover isolated helper functions — the merge logic, noise handling, and output format contract are entirely untested end-to-end. Tasks 1 and 2 close that coverage gap across the normal and degenerate-input paths; Task 3 is the one-line module export that makes `TranscriptSanitizer` injectable by any future `AnalyzeModule` consumer.
