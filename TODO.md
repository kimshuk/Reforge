# Daily Tasks — 2026-05-11
## Focus: NestJS Migration — Step 5: TranscriptSanitizerService

## Today's 3 Tasks

- [ ] **Implement pure text-transformation helpers (`normalizeText` and `formatTimestamp`)**
  - `normalizeText` is the single-snippet text cleaner: it strips leading `>` quote markers, removes bracket/paren noise via the existing `stripBracketNoise`, collapses Korean onomatopoeia runs and repeated punctuation, normalizes whitespace, and returns an empty string for lines that are entirely decorative symbols — cross-reference `normalizeText` in `backend/src/services/transcriptSanitizer.js` for the exact rules
  - `formatTimestamp` converts a raw seconds value to `MM:SS` or `H:MM:SS`; it must clamp NaN and negative inputs to zero so callers never need to guard against bad values — this function will be a named export because `LlmService` (Step 6) imports it independently to format timestamps in the LLM prompt
  - Both functions are pure with no side effects; add focused unit test cases covering empty/non-string input, Korean character collapsing, punctuation collapsing, and sub/super-hour timestamp formatting — tests serve as the completion gate for this task

- [ ] **Implement snippet flattening, sanitization pipeline, and segment builder**
  - Port `flattenRawSnippets` (recursively unwraps nested arrays to a flat list of objects) and `sanitizeSnippetList` (filters out snippets with invalid or negative `start`, normalizes each snippet's text, discards empties, sorts survivors by `startSec`) — these two together produce the clean, ordered input the segment builder expects
  - Port `shouldSplitSegment` and `buildSegments` using the exact threshold constants from the Express backend (`pauseSplitSeconds: 2.5`; soft caps at 35 s / 320 chars with a maturity check at 20 s / 180 chars; hard caps at 45 s / 420 chars); the split logic encodes the intent that a segment should be a meaningful, self-contained unit of speech — not an arbitrary time slice
  - `buildSegments` must assign sequential IDs (`S001`, `S002`, …), join each segment's snippet texts with a single space, and format `llmTranscriptText` as one `"S### | MM:SS | text"` line per segment — this exact string format is what the LLM prompt in Step 6 will receive as its transcript input

- [ ] **Wire `sanitize()`, export `formatTimestamp`, and verify the build**
  - Replace the throw-stub `sanitize()` with the real implementation: accept a raw snippet array, call `sanitizeSnippetList` then `buildSegments` in sequence, and return a fully typed `SanitizedTranscript` (`llmTranscriptText`, `segmentIndex`, `cleanedSnippetCount`) — this is the only public entry point that `AnalyzeService` (Step 7) will call
  - Ensure `formatTimestamp` is exported at the module level (not just as a private helper) so `LlmService` can import it in Step 6 without coupling to the entire `TranscriptSanitizer` class
  - Run `npm run build` in `backend-nest/` and confirm zero TypeScript errors; run `npm test` to confirm the existing `stripBracketNoise` spec and any new tests all pass — a clean build and green tests are the completion gate for Step 5

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
Step 5 is the blocking dependency for Steps 6–9 — nothing downstream can be built until the sanitizer produces a valid `SanitizedTranscript`. The three tasks are ordered by dependency: pure helpers first (no imports), then the pipeline that consumes them, then the public method and export that seal the contract for future callers.
