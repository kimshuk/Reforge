# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

Reforge is a YouTube video analysis app. Users paste a YouTube URL, the backend fetches the transcript via Python, sends it to OpenAI (GPT-4o-mini), and returns structured categories/keywords. The iOS client displays results in expandable chip layouts with real-time streaming progress.

## Repository Layout

```
ios/        — SwiftUI iOS app (Xcode project: NoteApp.xcodeproj)
backend/    — Node.js/Express API server
sample.json — Example /analyze response shape
```

## Development Commands

**iOS:**
```bash
open ios/NoteApp.xcodeproj   # Open in Xcode, then Cmd+R to run
```

**Backend:**
```bash
cd backend
npm install
npm run dev    # nodemon auto-reload
npm start      # production
```

**Backend requires Python** with `youtube-transcript-api` installed for transcript fetching.

**Backend URL config** (iOS): set `NOTEAPP_BACKEND_BASE_URL` env var, or add to `ios/.env`. Falls back to `http://localhost:3000`.

## iOS Architecture

MVVM with a protocol-based service layer:

- **`App/`** — `@main` entry point and root SwiftUI navigation
- **`Core/Networking/`** — Service protocols + implementations, models, config
  - `AnalyzeService` (protocol) / `URLSessionAnalyzeService` — streams POST `/analyze` via SSE using `URLSession.bytes(for:)`
  - `YouTubeOEmbedService` — checks video availability and auto-fills title
  - `AppConfig` — reads backend URL from env/Info.plist
  - `AnalyzeModels` — all Codable request/response types
- **`Features/Home/`** — The only feature module
  - `HomeViewModel` (`@MainActor`, `ObservableObject`) — all state and business logic
  - `HomeView` — SwiftUI view, reads from ViewModel
  - `AnalyzeResultView` — displays categories with expandable keyword chips

Services are injected via initializers, making them swappable. `HomeViewModel` owns both services.

## Backend Architecture

Express app with SSE streaming on the main endpoint:

- `POST /analyze` — accepts `{ url, title }`, streams Server-Sent Events: `progress` events during processing, then a final `result` event containing the JSON payload
- `GET /transcript/:id` — retrieves a stored transcript
- `GET /health` — health check

Pipeline: URL validation → Python subprocess (transcript fetch) → `transcriptSanitizer` → `transcriptValidator` → OpenAI structured output → JSON response

Error envelope shape: `{ error: { code, message } }` — the iOS client maps specific `code` strings (e.g. `TRANSCRIPT_UNAVAILABLE`, `OPENAI_CONTEXT_LENGTH_EXCEEDED`) to user-facing messages in `AnalyzeServiceError`.

## Key Implementation Details

- **SSE parsing** in `URLSessionAnalyzeService`: reads chunked bytes, buffers lines, parses `data:` prefixes. Handles concatenated JSON objects in a single chunk.
- **`PillFlowLayout`**: custom SwiftUI `Layout` protocol implementation for wrapping keyword pill views.
- **`KeyboardObserver`**: tracks keyboard height via `UIResponder` notifications for floating UI adjustments.
- **Streaming progress states**: `HomeViewModel.AnalysisState` enum drives UI during the fetch→sanitize→analyze pipeline.
- **No test targets** are currently configured on either iOS or backend.
