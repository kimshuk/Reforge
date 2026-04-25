# Daily Tasks — 2026-04-25
## Focus: NestJS Migration — Step 4: YoutubeService (Python subprocess)

## Today's 3 Tasks

- [ ] **Fix `extractVideoId` and define `TranscriptResult` type** — Add the missing `/shorts/` URL pattern to `extractVideoId` in `youtube.service.ts` (matches `backend/src/services/youtubeService.js:29–34`), then define a `TranscriptResult` interface `{ videoId: string; transcriptText: string; transcriptSnippets: unknown[]; languageCode: string | null; language: string | null; isGenerated: boolean | null }` and update `fetchTranscript`'s return type from `Promise<string>` to `Promise<TranscriptResult>`.

- [ ] **Implement `fetchTranscriptViaPython` private method** — Add a private async method that spawns `process.env.PYTHON_BIN ?? 'python3'` with `path.resolve(__dirname, '../../scripts/fetch_transcript.py')` and videoId (matching `backend/src/services/youtubeService.js:40–109`); collect stdout/stderr; on spawn `error` event throw `AppException(502, 'PYTHON_RUNTIME_ERROR', 'Unable to execute Python runtime')`; on non-zero exit code map stderr tokens: `PY_DEP_MISSING` → `AppException(500, 'PYTHON_DEPENDENCY_MISSING', ...)`, `TRANSCRIPT_UNAVAILABLE` → `AppException(502, 'TRANSCRIPT_UNAVAILABLE', ...)`, default → `AppException(502, 'TRANSCRIPT_FETCH_FAILED', ...)`; on exit code 0 parse stdout JSON (parse failure → `AppException(502, 'TRANSCRIPT_PARSE_FAILED', ...)`), normalize fields with the same type guards as lines 94–98 of the reference, and return the result.

- [ ] **Complete public `fetchTranscript` and verify build** — Update `fetchTranscript(url: string): Promise<TranscriptResult>` to call `this.extractVideoId(url)`, then `this.fetchTranscriptViaPython(videoId)`, throw `AppException(502, 'TRANSCRIPT_UNAVAILABLE', 'Transcript unavailable for this video')` when `transcriptText.trim()` is empty (matching `backend/src/services/youtubeService.js:116–118`), and return `{ videoId, ...rest }`; confirm `npm run build` inside `backend-nest/` passes with zero TypeScript errors.

## Migration Progress
**Completed steps:**
- 1 — Bootstrap NestJS scaffold (health module, main.ts, tsconfig strict mode)
- 2 — Project structure (analyze/ stubs, AnalyzeModule wired into AppModule)
- 3 — `AppException` class (`common/app.exception.ts`)
- 4 (partial) — `extractVideoId` URL parsing in `YoutubeService`

**Current step:** 4 — YoutubeService (completing Python subprocess + method wiring)
**Remaining steps:**
- 5 — TranscriptSanitizerService (sanitize raw transcript snippets → `llmTranscriptText` + `segmentIndex`)
- 6 — LlmService (OpenRouter call + structured output / source resolution)
- 7 — AnalyzeService (orchestrate URL → youtube → sanitize → llm, or text → sanitize → llm)
- 8 — AnalyzeController (POST /analyze with SSE streaming)
- 9 — AppExceptionFilter (finalize `{ error: { code, message } }` envelope + global registration)

## Why These Tasks
The three tasks split Step 4 at natural seams — type-level correctness first (interface + URL fix), then the async I/O core (subprocess + error mapping), then the public entry-point wiring with a build gate — so each task is independently reviewable and a failing build surfaces regressions immediately.
