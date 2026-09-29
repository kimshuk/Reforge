# Reforge

This repository contains the Reforge FastAPI backend and native iOS and Android clients for NoteApp.

## Repository layout

- `backend-fastapi/`: FastAPI service for transcript ingestion and clipping-oriented analysis
- `backend-nest/`: Legacy NestJS implementation retained during migration validation
- `ios/`: Native iOS app project (`NoteApp.xcodeproj`)
- `android/`: Native Android app project (Gradle Kotlin DSL)

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

Optional adaptive explanation enrichment is default-disabled. Set `EXPLANATION_ENRICHMENT_ENABLED=true` with the OpenAI provider to add occurrence-local, level-specific external citations. `EXPLANATION_ENRICHMENT_MAX_SOURCES` defaults to 3 and `EXPLANATION_ENRICHMENT_MAX_CONCURRENCY` defaults to 3. Other providers continue returning transcript-only explanations with empty citation arrays.

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

## Android app

Open the `android/` directory as the project in Android Studio. The application ID is
`com.andrewkim.reforge`. The app supports Android 8.0 (API 26) and later; compile and target
SDK are API 37. Use JDK 17 and install Android SDK Platform 37. Android Studio creates its own
untracked `local.properties` for the SDK path.

The Debug build defaults to `http://10.0.2.2:3000`, the Android emulator alias for a backend
running on the development computer. Start the backend on port 3000 before testing a new
YouTube share or Home analysis. A real device needs a backend address reachable from that
device; pass it as a Gradle property for the local build, for example:

```bash
cd android
./gradlew assembleDebug -PREFORGE_BACKEND_BASE_URL=http://YOUR_REACHABLE_HOST:3000
```

Replace `YOUR_REACHABLE_HOST` locally with a host that the device can reach. Do not commit a
developer address or local configuration. Release assembly and bundling require an explicitly
provided HTTPS backend URL; omission or HTTP fails the build. A Release build also needs the
normal signing and distribution setup outside this repository.

Run local checks from `android/`:

```bash
./gradlew clean testDebugUnitTest lintDebug assembleDebug
./gradlew connectedDebugAndroidTest
```

The connected test command needs one running API 37 emulator or compatible device. CI starts
one API 37 emulator and runs the same instrumented suite without sharding or parallel devices.

Manual share checklist on an emulator or a real device:

1. Launch Reforge normally; confirm Home and My Notes open independently.
2. Share a YouTube URL from another app. Confirm Reforge opens, shows progress, saves one note,
   and opens its detail without starting analysis.
3. Share the same URL again. Confirm the existing detail opens with no duplicate note.
4. Move the note to Trash and share again. Cancel once and confirm no change; repeat and Restore,
   confirming the original note and transcript return.
5. Share invalid text and text containing two different YouTube videos. Confirm the error and
   that Back returns to the originating task without creating a note.
6. Send another share while the first is loading, then rotate during loading. Confirm only the
   latest share completes and one detail opens.
7. Switch Home and My Notes, use Analyze from a note detail, and confirm the captured note
   input starts analysis. Return to each tab and confirm its prior destination.
8. Restart the app and confirm active and trashed notes persist. Return the app to foreground
   after an expired Trash item reaches 30 days; confirm it is removed.
