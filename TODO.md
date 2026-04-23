# Daily Tasks — 2026-04-23
## Focus: NestJS Migration — Step 1: Bootstrap NestJS Scaffold

## Today's 3 Tasks

- [ ] **Scaffold the NestJS project** — From `/home/user/Reforge/`, run `npx @nestjs/cli new backend-nest --package-manager npm --skip-git --strict` and verify that `backend-nest/src/main.ts`, `app.module.ts`, and `app.controller.ts` are generated before touching anything else.

- [ ] **Align `main.ts` with Express backend bootstrap** — Edit `backend-nest/src/main.ts` to cast the app as `NestExpressApplication`, call `app.use(express.json({ limit: '1mb' }))` (mirrors `backend/src/server.js:14`), read `PORT` from `process.env.PORT ?? 3000`, and log `"server.started"` with port on listen (mirrors `server.js:43–45`); update `package.json` scripts so `npm run dev` maps to `nest start --watch` and `npm start` maps to `nest start`, matching the Express backend's convention.

- [ ] **Wire `GET /health` and smoke-test the full bootstrap** — Replace the generated `AppController` stub with a `@Get('health')` handler returning `{ ok: true }` (mirrors `server.js:33–35`), run `npm run dev` inside `backend-nest/`, and confirm `curl -s http://localhost:3000/health` returns `{"ok":true}` — validating the entire scaffold before any feature module is added.

## Migration Progress
**Completed steps:** None — `backend-nest/` directory does not yet exist; Step 1 was planned on 2026-04-22 and again on 2026-04-23 but not executed.
**Current step:** 1 — Bootstrap NestJS scaffold
**Remaining steps:**
- 2 — Define project structure (create `analyze/` and `common/` with stub files)
- 3 — AppException class (`common/app.exception.ts`)
- 4 — YoutubeService (Python subprocess, URL → transcript text)
- 5 — TranscriptSanitizerService (sanitize raw transcript text)
- 6 — LlmService (OpenRouter call + structured output)
- 7 — AnalyzeService (orchestrate full pipeline)
- 8 — AnalyzeController (POST /analyze with SSE streaming)
- 9 — AppExceptionFilter (global `{ error: { code, message } }` envelope)

## Why These Tasks
The three tasks are strictly ordered bottom-up: the CLI must create the scaffold before `main.ts` can be customised, and the health smoke-test validates the entire bootstrap path — giving a known-good foundation before Step 2 adds the folder skeleton on top of it.
