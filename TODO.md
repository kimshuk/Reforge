# Daily Tasks — 2026-04-23
## Focus: NestJS Migration — Step 2 (finish) + Step 4: YoutubeService

## Today's 3 Tasks

- [ ] **Create `analyze/` stubs and wire AnalyzeModule** — Create `src/analyze/youtube.service.ts`, `transcript.sanitizer.ts`, `llm.service.ts`, and `analyze.service.ts` as `@Injectable()` classes with one method each throwing `new Error('not implemented')`; create `src/analyze/analyze.module.ts` declaring all four as providers; create `src/analyze/analyze.controller.ts` with `@Controller('analyze')` and a `@Post()` stub returning `{ ok: true }`; import `AnalyzeModule` in `src/app.module.ts`; verify `npm run build` inside `backend-nest/` passes with zero errors — this completes Step 2.

- [ ] **Implement `extractVideoId` in YoutubeService** — Port URL parsing from `backend/src/services/youtubeService.js:5–38` to TypeScript inside `YoutubeService`: handle `youtu.be`, `youtube.com/watch?v=`, `/shorts/`, and `m.youtube.com` patterns; throw `AppException(400, 'INVALID_YOUTUBE_URL', ...)` for unparseable URLs and unsupported formats; add a private `extractVideoId(url: string): string` method and call it from the public `fetchTranscriptText` stub.

- [ ] **Implement Python subprocess in YoutubeService** — Port `fetchTranscriptViaPython` from `backend/src/services/youtubeService.js:40–128` to TypeScript: spawn `process.env.PYTHON_BIN ?? 'python3'` with the resolved script path and video ID; collect stdout/stderr; on non-zero exit map `PY_DEP_MISSING` → `AppException(500, 'PYTHON_DEPENDENCY_MISSING', ...)` and `TRANSCRIPT_UNAVAILABLE` → `AppException(502, 'TRANSCRIPT_UNAVAILABLE', ...)`, default → `AppException(502, 'TRANSCRIPT_FETCH_FAILED', ...)`; on success parse JSON and resolve `{ videoId, transcriptText, transcriptSnippets, languageCode, language, isGenerated }`, throwing `AppException(502, 'TRANSCRIPT_UNAVAILABLE', ...)` when `transcriptText` is blank.

## Migration Progress
**Completed steps:**
- 1 — Bootstrap NestJS scaffold (health module, main.ts, tsconfig strict mode)
- 2 (partial) — `common/app.exception.ts` + `common/app-exception.filter.ts` stubs created; `AppException` class implemented

**Current step:** 2 (finish `analyze/` stubs) → 4 — YoutubeService
**Remaining steps:**
- 2 finish — `analyze/` directory stubs + AnalyzeModule wiring
- 4 — YoutubeService (Python subprocess, URL → transcript text) ← today's focus
- 5 — TranscriptSanitizerService (sanitize raw transcript text)
- 6 — LlmService (OpenRouter call + structured output)
- 7 — AnalyzeService (orchestrate full pipeline)
- 8 — AnalyzeController (POST /analyze with SSE streaming)
- 9 — AppExceptionFilter (global `{ error: { code, message } }` envelope, registered last)

## Why These Tasks
Task 1 unblocks everything else — no analyze service code can land until the module compiles cleanly. Tasks 2 and 3 are the two natural halves of Step 4: URL parsing is pure logic with no I/O (easy to unit-test in isolation), while the subprocess wrapper is the async I/O concern; splitting them keeps each task reviewable in a single sitting.
