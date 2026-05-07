# Daily Tasks — 2026-05-07
## Focus: NestJS Migration — Step 4: YoutubeService (Python subprocess)

## Today's 3 Tasks

- [ ] **Add `/shorts/` URL branch and `TranscriptResult` interface** — In `youtube.service.ts`, insert the `/shorts/` path check inside the `youtube.com`/`m.youtube.com` block after the `?v=` lookup (matching `backend/src/services/youtubeService.js:29–34`): `if (parsed.pathname.startsWith('/shorts/')) { const shortId = parsed.pathname.split('/')[2]; if (shortId) return shortId; }`; then declare a `TranscriptResult` interface `{ videoId: string; transcriptText: string; transcriptSnippets: unknown[]; languageCode: string | null; language: string | null; isGenerated: boolean | null }` and update `fetchTranscript`'s return type from `Promise<string>` to `Promise<TranscriptResult>`.

- [ ] **Implement `fetchTranscriptViaPython` private method** — Add `private fetchTranscriptViaPython(videoId: string): Promise<Omit<TranscriptResult, 'videoId'>>` that spawns `process.env.PYTHON_BIN ?? 'python3'` with `path.resolve(__dirname, '../../scripts/fetch_transcript.py')` and `videoId` (matching `youtubeService.js:40–109`); collect stdout/stderr via `data` events; on spawn `error` throw `AppException(502, 'PYTHON_RUNTIME_ERROR', 'Unable to execute Python runtime')`; on non-zero exit map stderr tokens: `PY_DEP_MISSING` → `AppException(500, 'PYTHON_DEPENDENCY_MISSING', 'Python package youtube-transcript-api is not installed')`, `TRANSCRIPT_UNAVAILABLE` → `AppException(502, 'TRANSCRIPT_UNAVAILABLE', 'Transcript unavailable for this video')`, default → `AppException(502, 'TRANSCRIPT_FETCH_FAILED', 'Unable to fetch YouTube transcript')`; on exit 0 parse stdout JSON (parse failure → `AppException(502, 'TRANSCRIPT_PARSE_FAILED', 'Invalid transcript response')`), normalize each field with the same type guards as `youtubeService.js:94–98`, and resolve with `{ transcriptText, transcriptSnippets, languageCode, language, isGenerated }`.

- [ ] **Wire `fetchTranscript` public method and verify build** — Replace the stub body of `fetchTranscript(url: string): Promise<TranscriptResult>` with: call `this.extractVideoId(url)` to get `videoId`, await `this.fetchTranscriptViaPython(videoId)`, throw `AppException(502, 'TRANSCRIPT_UNAVAILABLE', 'Transcript unavailable for this video')` when `transcriptText.trim()` is empty (matching `youtubeService.js:116–118`), and return `{ videoId, ...rest }`; then run `npm run build` inside `backend-nest/` and confirm zero TypeScript errors.

## Migration Progress
**Completed steps:**
- 1 — Bootstrap NestJS scaffold (health module, main.ts, tsconfig strict mode)
- 2 — Project structure (analyze/ and common/ stubs, AnalyzeModule wired into AppModule)
- 3 — AppException class (common/app.exception.ts)

**Current step:** 4 — YoutubeService (extractVideoId partial; /shorts/ branch, Python subprocess, and public method wiring still missing)

**Remaining steps:**
- 5 — TranscriptSanitizerService (sanitize raw transcript snippets → cleaned text)
- 6 — LlmService (OpenRouter call + structured output: categories + keywords)
- 7 — AnalyzeService (orchestrate URL → youtube → sanitize → llm, or text → sanitize → llm)
- 8 — AnalyzeController (POST /analyze with SSE streaming)
- 9 — AppExceptionFilter (finalize { error: { code, message } } envelope + global registration)

## Why These Tasks
Step 4 carries into a fourth day with all three sub-tasks still pending against an unchanged stub; they remain ordered by compile dependency (type contract first, then private impl, then public wiring + build gate) so each task compiles cleanly before the next begins.
