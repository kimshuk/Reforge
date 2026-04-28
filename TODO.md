# Daily Tasks — 2026-04-28
## Focus: NestJS Migration — Step 4: YoutubeService (Python subprocess)

## Today's 3 Tasks

- [ ] **Add `/shorts/` URL branch and `TranscriptResult` type** — In `youtube.service.ts`, insert the `/shorts/` path check inside the `youtube.com`/`m.youtube.com` block after the `?v=` lookup (matching `backend/src/services/youtubeService.js:29–34`): `if (parsed.pathname.startsWith('/shorts/')) { const shortId = parsed.pathname.split('/')[2]; if (shortId) return shortId; }`; then declare a `TranscriptResult` interface `{ videoId: string; transcriptText: string; transcriptSnippets: unknown[]; languageCode: string | null; language: string | null; isGenerated: boolean | null }` and update `fetchTranscript`'s return type from `Promise<string>` to `Promise<TranscriptResult>`.

- [ ] **Implement `fetchTranscriptViaPython` private method** — Add `private fetchTranscriptViaPython(videoId: string): Promise<Omit<TranscriptResult, 'videoId'>>` that spawns `process.env.PYTHON_BIN ?? 'python3'` with `path.resolve(__dirname, '../../scripts/fetch_transcript.py')` and `videoId` (matching `youtubeService.js:40–109`); collect stdout/stderr via `data` events; on spawn `error` throw `AppException(502, 'PYTHON_RUNTIME_ERROR', 'Unable to execute Python runtime')`; on non-zero exit map stderr tokens: `PY_DEP_MISSING` → `AppException(500, 'PYTHON_DEPENDENCY_MISSING', 'Python package youtube-transcript-api is not installed')`, `TRANSCRIPT_UNAVAILABLE` → `AppException(502, 'TRANSCRIPT_UNAVAILABLE', 'Transcript unavailable for this video')`, default → `AppException(502, 'TRANSCRIPT_FETCH_FAILED', 'Unable to fetch YouTube transcript')`; on exit 0 parse stdout JSON (parse failure → `AppException(502, 'TRANSCRIPT_PARSE_FAILED', 'Invalid transcript response')`), normalize each field with the same type guards as `youtubeService.js:94–98`, and resolve with `{ transcriptText, transcriptSnippets, languageCode, language, isGenerated }`.

- [ ] **Wire `fetchTranscript` public method and verify build** — Replace the stub body of `fetchTranscript(url: string): Promise<TranscriptResult>` with: call `this.extractVideoId(url)` to get `videoId`, await `this.fetchTranscriptViaPython(videoId)`, throw `AppException(502, 'TRANSCRIPT_UNAVAILABLE', 'Transcript unavailable for this video')` when `transcriptText.trim()` is empty (matching `youtubeService.js:116–118`), and return `{ videoId, ...rest }`; then run `npm run build` inside `backend-nest/` and confirm zero TypeScript errors.

## Migration Progress
**Completed steps:**
- 1 — Bootstrap NestJS scaffold (health module, main.ts, tsconfig strict mode)
- 2 — Project structure (analyze/ and common/ stubs, AnalyzeModule wired into AppModule)
- 3 — AppException class (common/app.exception.ts)
- 4 (partial) — extractVideoId URL parsing in YoutubeService (shorts branch + subprocess still missing)

**Current step:** 4 — YoutubeService (completing /shorts/ URL branch, Python subprocess, and public method wiring)

**Remaining steps:**
- 5 — TranscriptSanitizerService (sanitize raw transcript snippets → cleaned text + segment index)
- 6 — LlmService (OpenRouter call + structured output: categories + keywords)
- 7 — AnalyzeService (orchestrate URL → youtube → sanitize → llm, or text → sanitize → llm)
- 8 — AnalyzeController (POST /analyze with SSE streaming)
- 9 — AppExceptionFilter (finalize { error: { code, message } } envelope + global registration)

## Why These Tasks
Step 4 was planned on 2026-04-27 but not executed, so these are the same three tasks carried forward; the sequencing is type-contract first (Task 1), subprocess I/O internals second (Task 2), then public-method wiring with a build gate (Task 3) so TypeScript errors surface before any runtime behavior is reachable.
