# Daily Tasks — 2026-04-22
## Focus: NestJS Migration

## Today's 3 Tasks

- [ ] **Bootstrap NestJS app scaffold** — Create `backend-nest/` with NestJS CLI init, wire `main.ts` bootstrap (JSON body parser, 1 MB limit, global prefix), and add `AppModule` with a `GET /health` controller that mirrors `server.js`'s health check; confirm `npm run start:dev` serves `{"ok":true}`.
- [ ] **Port AppError → AppException + global exception filter** — Translate `middleware/errorHandler.js` into a NestJS `AppException extends HttpException` class and a `@Catch()` `AppExceptionFilter` that preserves the `{ error: { code, message } }` envelope the iOS client depends on; register it globally in `main.ts` and add a `RequestIdInterceptor` that attaches `req.requestId` + logs method/path/status/duration via the NestJS `Logger`.
- [ ] **Create TranscriptModule (service + controller)** — Migrate `transcriptStore.js` to a singleton `@Injectable()` `TranscriptStoreService` implementing `OnModuleDestroy` to clear the cleanup interval, then wire `GET /transcript/:transcriptId` in `TranscriptController`, using `AppExceptionFilter` to emit `TRANSCRIPT_NOT_FOUND` on miss and `INVALID_TRANSCRIPT_ID` on bad UUID — confirming the response shape matches the Express route exactly.

## Migration Progress
**Done:**
- Full Express backend feature-complete (server.js, analyze route with SSE, transcript route, errorHandler, all services)
- Python subprocess integration for YouTube transcript fetching (`scripts/fetch_transcript.py`)
- OpenAI structured output with JSON schema (`openaiService.js`, `promptBuilder.js`)
- Transcript sanitizer, validator, in-memory TTL store
- iOS client consuming the Express API

**Remaining (all NestJS equivalents):**
- NestJS project scaffold (main.ts, AppModule, bootstrap config)
- AppException class + global exception filter preserving `{ error: { code, message } }` envelope
- RequestId middleware + HTTP request logging interceptor
- Health endpoint (`GET /health`)
- TranscriptModule: `TranscriptStoreService` (TTL Map + OnModuleDestroy cleanup) + `TranscriptController` (`GET /transcript/:id`)
- AnalyzeModule: `AnalyzeController` (SSE streaming via `@Res()` + manual header flushing) + `AnalyzeService` (orchestrates YouTube → sanitize → OpenAI pipeline)
- YoutubeService (Python subprocess spawn with AppException error mapping)
- OpenAiService (structured output call + source-ref resolution)
- PromptBuilderService (prompt construction + JSON schema)
- TranscriptSanitizerService + TranscriptValidatorService (body validation, UUID checks)
- ConfigModule wiring (dotenv, OpenAI client instantiation)

## Why These Tasks
Nothing has been migrated yet, so today lays the only viable foundation: the scaffold must exist before any module can be written, the error filter must exist before any controller can throw typed errors, and `TranscriptModule` is the simplest controller/service pair to validate the full request → service → response → filter pipeline before tackling the complex SSE streaming in `AnalyzeModule` tomorrow.
