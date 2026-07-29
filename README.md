# Reforge

This repository contains the Reforge FastAPI backend and the native iOS client for NoteApp.

## Repository layout

- `backend-fastapi/`: FastAPI service for transcript ingestion and clipping-oriented analysis
- `backend-nest/`: Legacy NestJS implementation retained during migration validation
- `ios/`: Native iOS app project (`NoteApp.xcodeproj`)

## Backend

The backend runs as a full local stack:

```bash
docker compose up
```

This starts `backend-fastapi`, Postgres, and Redis. Docker Compose reads
`backend-fastapi/.env`, with `backend-nest/.env` retained as a temporary migration fallback.

Requirements:

- Python 3.12+
- At least one configured LLM API key, such as `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `GEMINI_API_KEY`

Backend development:

```bash
cd backend-fastapi
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

Create `backend-fastapi/.env` from `backend-fastapi/.env.example` and set the keys you need.
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
cd backend-fastapi
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload --port 3000
```

The backend exposes:

- `GET /health`
- `POST /analyze`
- `POST /analyze?stream=progress`
- `GET /transcript/:transcriptId`

`POST /analyze` returns semantic categories containing contextual keyword occurrences. Categories group related occurrences and do not have timestamps. Every keyword occurrence has a stable `candidateClippingId`, its own explanation ladder, and its own timestamped source; repeated display terms are valid when they come from different transcript sections.

## iOS app

Requirements:

- Xcode
- A local `ios/.env` file based on `ios/.env.example`

Open the project:

```bash
open ios/NoteApp.xcodeproj
```

The iOS source currently lives under `ios/App`, `ios/Core`, and `ios/UI`.

The `NoteAppTests` Xcode target covers modern occurrence IDs, duplicate display terms, occurrence-specific explanations and timestamps, and deterministic legacy fallback IDs. Run it with Product > Test in Xcode or:

```bash
xcodebuild test -project ios/NoteApp.xcodeproj -scheme NoteApp -destination 'platform=iOS Simulator,name=iPhone 16'
```

## Notes

- Project-specific ignore rules are kept in each service and client directory.
- Virtual environments, dependency directories, and local `.env` files are intentionally ignored.
