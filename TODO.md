# Daily Tasks — 2026-04-24
## Focus: NestJS Migration — Step 2 (finish) + Step 4: YoutubeService

## Today's 3 Tasks

- [ ] **Create `analyze/` stubs and wire AnalyzeModule** — Create `src/analyze/youtube.service.ts`, `transcript.sanitizer.ts`, `llm.service.ts`, `analyze.service.ts` as `@Injectable()` classes with one method each throwing `new Error('not implemented')`; create `src/analyze/analyze.module.ts` declaring all four as providers; create `src/analyze/analyze.controller.ts` with `@Controller('analyze')` and a `@Post()` stub returning `{ ok: true }`; import `AnalyzeModule` in `src/app.module.ts`; verify `npm run build` inside `backend-nest/` passes with zero errors — this completes Step 2.

- [ ] **Implement `extractVideoId` in YoutubeService** — Port URL parsing from `backend/src/services/youtubeService.js:5–38` to TypeScript inside `YoutubeService`: handle `youtu.be`, `youtube.com/watch?v=`, `/shorts/`, and `m.youtube.com` patterns; throw `new AppException(400, 'INVALID_YOUTUBE_URL', ...)` for unparseable URLs; add a private `extractVideoId(url: string): string` method and call it from the public `fetchTranscript` stub; verify the method resolves the correct ID for all four URL formats.

- [ ] **Implement Python subprocess in YoutubeService** — Port `fetchTranscriptViaPython` from `backend/src/services/youtubeService.js:40–128` to TypeScript: spawn `process.env.PYTHON_BIN ?? 'python3'` with the resolved script path and video ID; collect stdout/stderr; on non-zero exit map `PY_DEP_MISSING` → `AppException(500, 'PYTHON_DEPENDENCY_MISSING', ...)`, `TRANSCRIPT_UNAVAILABLE` → `AppException(502, 'TRANSCRIPT_UNAVAILABLE', ...)`, default → `AppException(502, 'TRANSCRIPT_FETCH_FAILED', ...)`; on success parse JSON and return `{ videoId, transcriptText, transcriptSnippets, languageCode, language, isGenerated }`, throwing `AppException(502, 'TRANSCRIPT_UNAVAILABLE', ...)` when `transcriptText` is blank.

## Migration Progress
**Completed steps:**
- 1 — Bootstrap NestJS scaffold (health module, main.ts, tsconfig strict mode)
- 3 — `AppException` class implemented in `common/app.exception.ts`

**Current step:** 2 (finish `analyze/` stubs + AnalyzeModule wiring) → 4 — YoutubeService
**Remaining steps:**
- 2 finish — `analyze/` directory stubs + AnalyzeModule wiring
- 4 — YoutubeService (Python subprocess, URL → transcript text) ← today's focus
- 5 — TranscriptSanitizerService (sanitize raw transcript text)
- 6 — LlmService (OpenRouter call + structured output)
- 7 — AnalyzeService (orchestrate full pipeline)
- 8 — AnalyzeController (POST /analyze with SSE streaming)
- 9 — AppExceptionFilter (global `{ error: { code, message } }` envelope, registered last)

## Why These Tasks
Task 1 is the prerequisite for everything: no analyze service can compile until the module is wired. Tasks 2 and 3 split Step 4 at its natural seam — pure URL-parsing logic (no I/O, easy to verify inline) versus the async subprocess wrapper — keeping each task reviewable in a single sitting.
