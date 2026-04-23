# Daily Tasks — 2026-04-23
## Focus: NestJS Migration — Step 1: Bootstrap NestJS Scaffold

## Today's 3 Tasks

- [ ] **Initialize NestJS project and configure scripts** — Run `nest new backend-nest --package-manager npm --skip-git`, update `tsconfig.json` for strict mode, and align `package.json` scripts so `npm run dev` maps to `start:dev --watch` and `npm start` maps to `start:prod`, matching the Express backend's dev/prod conventions.

- [ ] **Wire `main.ts` with Express-parity bootstrap settings** — Configure `main.ts` to apply `express.json({ limit: '1mb' })` via `app.use()`, read `PORT` from `process.env.PORT || 3000`, attach the NestJS `Logger`, and log a `server.started` message on listen — replicating the behaviour in `server.js` lines 14 and 43–45 exactly.

- [ ] **Add `AppModule` with `GET /health` and smoke-test the stack** — Create `AppController` with `@Get('health')` returning `{ ok: true }` (mirroring `server.js:33–35`), wire it into `AppModule`, then run `npm run start:dev` and confirm `curl localhost:3000/health` returns `{"ok":true}` so the full bootstrap path is validated before any feature module is added.

## Migration Progress
**Completed steps:** None — `backend-nest/` directory does not exist; Step 1 was planned on 2026-04-22 but not executed.
**Current step:** 1 — Bootstrap NestJS scaffold
**Remaining steps:**
- 1 — Bootstrap NestJS scaffold (today)
- 2 — Define project structure (all module folders + stub files)
- 3 — ConfigModule (dotenv / env vars)
- 4 — AppException class (single throwable, no filter yet)
- 5 — TranscriptModule (TranscriptStoreService + GET /transcript/:id)
- 6 — YoutubeService (Python subprocess + AppException error mapping)
- 7 — TranscriptSanitizerService + TranscriptValidatorService
- 8 — PromptBuilderService + OpenAiService
- 9 — AnalyzeModule (POST /analyze SSE streaming)
- 10 — Global exception filter + RequestId interceptor

## Why These Tasks
The three tasks build strictly bottom-up: the CLI init must exist before `main.ts` can be customised, and `main.ts` must be wired before the health controller can be smoke-tested — validating the entire bootstrap path in one day so Step 2 (folder structure) can start from a known-good scaffold tomorrow.
