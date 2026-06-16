# Reforge

This repository contains the current Reforge backend and the native iOS client for NoteApp.

## Repository layout

- `backend/`: Node.js / Express API for transcript ingestion and category analysis
- `ios/`: Native iOS app project (`NoteApp.xcodeproj`)

## Backend

The Nest backend can run as a full local stack:

```bash
docker compose up
```

This starts `backend-nest`, Postgres, and Redis. Set LLM API keys in your shell
or a root `.env` file before starting Docker Compose.

Requirements:

- Node.js 18+
- Python 3 available as `python3` or via `PYTHON_BIN`
- `youtube-transcript-api` installed in that Python environment
- OpenAI API key

Setup:

```bash
cd backend
npm install
```

Create `backend/.env` with at least:

```env
OPENAI_API_KEY=your_api_key_here
PORT=3000
```

Run the API:

```bash
cd backend
npm run dev
```

The backend exposes:

- `GET /health`
- `POST /analyze`
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

- Project-specific ignore rules are kept in `backend/.gitignore` and `ios/.gitignore`; the root `.gitignore` only covers repo-wide artifacts.
- `backend/node_modules/` and local `.env` files are intentionally ignored and should not be committed.
