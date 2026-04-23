# Daily Tasks — 2026-04-23
## Focus: NestJS Migration — Step 2: Define Project Structure

## Today's 3 Tasks

- [ ] **Create `common/` stubs** — Create `src/common/app.exception.ts` with a skeleton `AppException extends Error` class carrying `statusCode`, `code`, and `message` fields (matching `backend/src/middleware/errorHandler.js:3–9`), and `src/common/app-exception.filter.ts` with an empty `@Catch(AppException) AppExceptionFilter` class stub — both left intentionally incomplete; full implementations come in Steps 3 and 9.

- [ ] **Create `analyze/` service stubs** — Create stub `@Injectable()` classes for `src/analyze/youtube.service.ts` (single `fetchTranscriptText(youtubeUrl: string)` method signature, mirrors `backend/src/services/youtubeService.js:89`), `src/analyze/transcript.sanitizer.ts` (single `sanitize(rawSnippets: unknown[])` method signature, mirrors `transcriptSanitizer.js:178`), `src/analyze/llm.service.ts` (single `analyzeCategories(payload: unknown)` method signature, mirrors `backend/src/services/openaiService.js`), and `src/analyze/analyze.service.ts` (single `analyze(body: unknown)` method signature) — each method body throws `new Error('not implemented')`.

- [ ] **Create `AnalyzeModule` + `AnalyzeController` and wire into `AppModule`** — Create `src/analyze/analyze.module.ts` declaring all four analyze services as providers and `AnalyzeController` as its controller, create `src/analyze/analyze.controller.ts` with `@Controller('analyze')` and a `@Post()` handler returning `{ ok: true }` as a placeholder, update `src/app.module.ts` to import `AnalyzeModule`, then verify with `npm run build` inside `backend-nest/` that TypeScript compilation succeeds with zero errors — the full structure must compile before Step 3 begins.

## Migration Progress
**Completed steps:** 1 — Bootstrap NestJS scaffold (`feat: bootstrap NestJS app scaffold with health check`, `chore: strict mode tsconfig and dev script alias`)
**Current step:** 2 — Define project structure (create `analyze/` and `common/` with stub files)
**Remaining steps:**
- 3 — AppException class (`common/app.exception.ts`)
- 4 — YoutubeService (Python subprocess, URL → transcript text)
- 5 — TranscriptSanitizerService (sanitize raw transcript text)
- 6 — LlmService (OpenRouter call + structured output)
- 7 — AnalyzeService (orchestrate full pipeline)
- 8 — AnalyzeController (POST /analyze with SSE streaming)
- 9 — AppExceptionFilter (global `{ error: { code, message } }` envelope)

## Why These Tasks
Tasks 1 and 2 are independent and can be done in parallel — common stubs have no deps on analyze services and vice versa. Task 3 depends on both (it imports and wires them into the module), so it must come last; ending with a clean `npm run build` gives a verified compile baseline before any real logic lands in Step 3.
