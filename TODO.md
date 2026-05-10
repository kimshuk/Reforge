# Daily Tasks — 2026-05-10
## Focus: NestJS Migration — Step 5: TranscriptSanitizerService (continued)

## Today's 3 Tasks

- [ ] **Implement `normalizeText` and `formatTimestamp`**
  - Port `normalizeText`: strip leading `>` characters, apply bracket-noise removal via the existing `stripBracketNoise`, collapse Korean onomatopoeia runs (`ㅋㅋㅋ…` → `ㅋㅋ`, `ㅎㅎㅎ…` → `ㅎㅎ`), collapse repeated punctuation runs (`!!!` → `!!`), normalize whitespace, and return an empty string for lines that are purely decorative symbols — cross-reference `normalizeText` in `backend/src/services/transcriptSanitizer.js`
  - Port `formatTimestamp`: convert a raw seconds value to `MM:SS` for videos under an hour, or `H:MM:SS` for longer ones; guard against negative and NaN input by clamping to zero — this function is a named export that `LlmService` will depend on in Step 6
  - Both functions are pure and side-effect-free; add unit test cases for each (empty input, Korean chars, punctuation runs, sub/super-hour timestamps) so correctness is locally verifiable without running the full pipeline

- [ ] **Implement snippet processing and segment building**
  - Port `sanitizeSnippetList`: iterate raw snippets, skip entries with invalid or negative `start` values, normalize each snippet's text via `normalizeText`, discard snippets that are empty after normalization, then sort the survivors by `startSec` — this produces the clean, ordered input that the segment builder expects
  - Port `shouldSplitSegment` and `buildSegments` using the exact threshold constants from the Express backend (`pauseSplitSeconds: 2.5`, soft caps at 35 s / 320 chars with a maturity check, hard caps at 45 s / 420 chars); the split decision encodes the intent that segments should be meaningful, self-contained units of speech rather than arbitrary time slices
  - `buildSegments` must assign sequential IDs (`S001`, `S002`, …), join each segment's constituent snippet texts with a single space, and format `llmTranscriptText` as one `"S### | MM:SS | text"` line per segment — this exact format is what the LLM prompt in Step 6 expects as its transcript input

- [ ] **Wire `sanitize` method, export `formatTimestamp`, and verify build**
  - Replace the throw-stub `sanitize()` with the real implementation: accept a raw snippet array, call `sanitizeSnippetList` then `buildSegments` in sequence, and return the fully typed `SanitizedTranscript` shape (`llmTranscriptText`, `segmentIndex`, `cleanedSnippetCount`) — this is the only public entry point callers use
  - Ensure `formatTimestamp` is exported from the module (named export or public method on the service) so `LlmService` can import it in Step 6 without importing the entire service class
  - Run `npm run build` in `backend-nest/` and confirm zero TypeScript errors; run `npm test` to confirm the existing `stripBracketNoise` spec and any new tests all pass — a clean build is the completion gate for this step

## Migration Progress
**Completed steps:**
- 1 — Bootstrap NestJS scaffold (health module, main.ts, tsconfig strict mode)
- 2 — Project structure (analyze/ and common/ stubs, AnalyzeModule wired into AppModule)
- 3 — AppException class (common/app.exception.ts)
- 4 — YoutubeService (Python subprocess, URL → transcript text, error classification)

**Current step:** 5 — TranscriptSanitizerService (interfaces + bracket-noise done; normalizeText, formatTimestamp, snippet pipeline, and sanitize() still outstanding)

**Remaining steps:**
- 6 — LlmService (OpenRouter call + structured output: categories + keywords)
- 7 — AnalyzeService (orchestrate URL → youtube → sanitize → llm, or text → sanitize → llm)
- 8 — AnalyzeController (POST /analyze with SSE streaming)
- 9 — AppExceptionFilter (finalize { error: { code, message } } envelope + global registration)

## Why These Tasks
These three tasks complete Step 5 in dependency order — pure helper functions first (normalizeText, formatTimestamp), then the pipeline that consumes them (snippet processing and segmenting), then the public API that ties everything together — so each task leaves the codebase in a buildable, testable state and Step 6 (LlmService) can start with a fully working sanitizer to call.
