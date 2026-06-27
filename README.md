# Reforge

This repository contains the current Reforge NestJS backend and the native iOS client for NoteApp.

## Repository layout

- `backend-nest/`: NestJS API for transcript ingestion and clipping-oriented analysis
- `ios/`: Native iOS app project (`NoteApp.xcodeproj`)

## Backend

The backend runs as a full local stack:

```bash
docker compose up
```

This starts `backend-nest`, Postgres, and Redis. Docker Compose reads
`backend-nest/.env`, so put your LLM API keys there before starting the stack.

Requirements:

- Node.js 18+
- Python 3 available as `python3` or via `PYTHON_BIN`
- `youtube-transcript-api` installed in that Python environment
- At least one configured LLM API key, such as `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `GEMINI_API_KEY`

Backend development:

```bash
cd backend-nest
npm install
```

Create `backend-nest/.env` from `backend-nest/.env.example` and set the keys you need.
For the Docker stack, the default services use:

```env
PORT=3000
DATABASE_URL=postgres://reforge:reforge@postgres:5432/reforge
REDIS_URL=redis://redis:6379
LLM_PROVIDER=openai
OPENAI_API_KEY=your_api_key_here
```

Run the API:

```bash
cd backend-nest
npm run dev
```

The backend exposes:

- `GET /health`
- `POST /analyze`
- `POST /analyze?stream=progress`
- `GET /transcript/:transcriptId`

## iOS app

Requirements:

- Xcode
- A local `ios/.env` file based on `ios/.env.example`

Open the project:

```bash
open ios/NoteApp.xcodeproj
```

The iOS source currently lives under `ios/App`, `ios/Core`, and `ios/UI`.

## Notes

- Project-specific ignore rules are kept in `backend-nest/.gitignore` and `ios/.gitignore`; the root `.gitignore` only covers repo-wide artifacts.
- `backend-nest/node_modules/` and local `.env` files are intentionally ignored and should not be committed.
