# Daily Tasks — 2026-05-28
## Focus: NestJS Migration — Step 5: TranscriptSanitizerService

## Today's 3 Tasks

- [ ] **Implement `sanitize()` method body**
  - The method needs the correct signature `sanitize(rawSnippets: RawSnippet[], options?: SegmentOptions): SanitizedTranscript` — all the required types (`RawSnippet`, `SegmentOptions`, `SanitizedTranscript`) are already defined in the same file, so no new imports are needed.
  - Inside, call `sanitizeSnippetList(rawSnippets)` to get the cleaned, timestamp-sorted snippet array; capture its length as `cleanedSnippetCount` before passing the array and `options` to `buildSegments()`, which returns `llmTranscriptText` and `segmentIndex`.
  - Return all three fields as a `SanitizedTranscript` object — `cleanedSnippetCount` is the downstream coverage metric `AnalyzeService` will log, so it must reflect only the snippets that survived normalization (valid timestamp + non-empty text), not the raw input length.
  - Done when the method no longer throws and `npm run build` exits with zero TypeScript errors.

- [ ] **Add unit tests for `sanitize()` in the existing spec file**
  - The current `transcript.sanitizer.spec.ts` only tests the three exported helpers (`stripBracketNoise`, `normalizeText`, `formatTimestamp`); the class method itself has no coverage — add a `describe('TranscriptSanitizer.sanitize')` block that instantiates the class directly (no NestJS DI needed in unit tests).
  - Write at minimum four test cases: a happy-path batch of valid snippets (assert `cleanedSnippetCount` equals the number of valid inputs, that every `segmentIndex` entry has `id`/`startSec`/`endSec`/`text` fields, and that each `llmTranscriptText` line matches the `S001 | MM:SS | text` format); an empty array input (expect `cleanedSnippetCount === 0`, empty `segmentIndex`, and an empty string for `llmTranscriptText`); a batch where every snippet has an invalid timestamp or text that normalizes to empty (expect `cleanedSnippetCount === 0`); and a single-snippet input to verify the base case doesn't split into multiple segments.
  - Done when `npm test` shows the new describe block passing alongside the existing helper tests.

- [ ] **Build + test verification and DI wiring confirmation**
  - Run `npm run build && npm test` inside `backend-nest/` and confirm both commands exit cleanly — the strict tsconfig may surface type issues (e.g., missing explicit return types or unchecked `unknown` values) that hand-writing the method alone won't reveal.
  - Cross-check `analyze.module.ts` to confirm `TranscriptSanitizer` is listed in `exports` as well as `providers` — `AnalyzeService` (Step 7) will inject it, and unless it is exported from the module NestJS will throw a DI error at bootstrap time; fix the module declaration now rather than during Step 7.
  - Done when both commands pass with zero errors and the module declaration is correct for downstream injection.

## Migration Progress
**Completed steps:**
- 1 — Bootstrap NestJS scaffold (main.ts, app.module.ts, tsconfig strict mode)
- 2 — Project structure (analyze/ and common/ stubs, AnalyzeModule wired into AppModule)
- 3 — AppException class (common/app.exception.ts)
- 4 — YoutubeService (Python subprocess, URL → transcript text, error classification)

**Current step:** 5 — TranscriptSanitizerService (`sanitize()` method remaining)

**Remaining steps:**
- 6 — LlmService (OpenRouter call + structured output)
- 7 — AnalyzeService (orchestrate URL → youtube → sanitize → llm, or text → sanitize → llm)
- 8 — AnalyzeController (POST /analyze with SSE streaming)
- 9 — AppExceptionFilter (finalize `{ error: { code, message } }` envelope + global registration)

## Why These Tasks
All the helper logic for Step 5 is already implemented as module-level functions — closing it is one focused method body plus tests, and verifying DI wiring now prevents the typed `SanitizedTranscript` contract from being a hidden landmine when `LlmService` and `AnalyzeService` depend on it in Steps 6 and 7.
