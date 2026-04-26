# Daily Tasks — 2026-04-26
## Focus: NestJS Migration — Step 4: YoutubeService (Python subprocess)

## Today's 3 Tasks

- [ ] **Add `/shorts/` URL pattern and `TranscriptResult` type** — In `youtube.service.ts`, add the missing `/shorts/` branch inside the `youtube.com` host block (after the `?v=` check, matching `backend/src/services/youtubeService.js:29–34`); then declare a `TranscriptResult` interface `{ videoId: string; transcriptText: string; transcriptSnippets: unknown[]; languageCode: string | null; language: string | null; isGenerated: boolean | null }` and update `fetchTranscript`'s return type from `Promise<string>` to `Promise<TranscriptResult>`.

- [ ] **Implement `fetchTranscriptViaPython` private method** — Add a private async method that spawns `process.env.PYTHON_BIN ?? 'python3'` with `path.resolve(__dirname, '../../scripts/fetch_transcript.py')` and `videoId` (matching `backend/src/services/youtubeService.js:40–109`); collect stdout/stderr via data events; on spawn `error` event throw `AppException(502, 'PYTHON_RUNTIME_ERROR', 'Unable to execute Python runtime')`; on non-zero exit code map stderr tokens: `PY_DEP_MISSING` → `AppException(500, 'PYTHON_DEPENDENCY_MISSING', 'Python package youtube-transcript-api is not installed')`, `TRANSCRIPT_UNAVAILABLE` → `AppException(502, 'TRANSCRIPT_UNAVAILABLE', 'Transcript unavailable for this video')`, default → `AppException(502, 'TRANSCRIPT_FETCH_FAILED', 'Unable to fetch YouTube transcript')`; on exit code 0 parse stdout JSON (parse failure → `AppException(502, 'TRANSCRIPT_PARSE_FAILED', 'Invalid transcript response')`), normalize fields with the same type guards as lines 94–98 of the reference, and return `Omit<TranscriptResult, 'videoId'>`.

- [ ] **Wire `fetchTranscript` public method and verify build** — Replace the stub body of `fetchTranscript(url: string): Promise<TranscriptResult>` with: call `this.extractVideoId(url)`, then `this.fetchTranscriptViaPython(videoId)`, throw `AppException(502, 'TRANSCRIPT_UNAVAILABLE', 'Transcript unavailable for this video')` when `transcriptText.trim()` is empty (matching `backend/src/services/youtubeService.js:116–118`), and return `{ videoId, ...rest }`; then run `npm run build` inside `backend-nest/` and confirm zero TypeScript errors.

## Migration Progress
**Completed steps:**
- 1 — Bootstrap NestJS scaffold (health module, main.ts, tsconfig strict mode)
- 2 — Project structure (analyze/ and common/ stubs, AnalyzeModule wired into AppModule)
- 3 — `AppException` class (`common/app.exception.ts`)
- 4 (partial) — `extractVideoId` URL parsing in `YoutubeService` (shorts branch + subprocess missing)

**Current step:** 4 — YoutubeService (completing Python subprocess + method wiring)
**Remaining steps:**
- 5 — TranscriptSanitizerService (sanitize raw transcript snippets → cleaned text)
- 6 — LlmService (OpenRouter call + structured output: categories + keywords)
- 7 — AnalyzeService (orchestrate URL → youtube → sanitize → llm, or text → sanitize → llm)
- 8 — AnalyzeController (POST /analyze with SSE streaming)
- 9 — AppExceptionFilter (finalize `{ error: { code, message } }` envelope + global registration)

## Why These Tasks
Step 4 was partially committed (URL parsing only) so the subprocess I/O — the riskiest and most behaviorally complex piece — remains unbuilt; splitting it into type-contract first, then subprocess internals, then public-method wiring with a build gate keeps each task independently reviewable and surfaces type errors before the runtime path is wired in.
