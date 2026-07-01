# Web Frontend Migration — Design

**Date:** 2026-07-01
**Status:** Approved (brainstorming) — ready for implementation planning

## Goal

Build a mobile-first web frontend for Reforge that consumes the existing NestJS
`POST /analyze` SSE endpoint. Migration away from the SwiftUI iOS client, which
stays in the repo untouched for now. This is a **web redesign**, not a 1:1 port
of the iOS interaction — but it preserves the product's core features: streaming
progress, the categories/keywords result, and keyword **curation**.

## Decisions (from brainstorming)

- **Scope:** Redesign for web (not literal iOS parity, not a stripped MVP).
- **Stack:** Vite + React + TypeScript. Client-only SPA, static build. No SSR
  (the app is a client that streams from the backend — no SEO/SSR need).
- **oEmbed:** Dropped. iOS called YouTube oEmbed client-side for title autofill +
  availability pre-check; browsers can't (no CORS on YouTube's oEmbed endpoint).
  - Thumbnail derived from `videoId` directly: `https://img.youtube.com/vi/{id}/hqdefault.jpg`
    (plain `<img>`, no CORS).
  - No title autofill — `title` is optional on the backend (`AnalyzeRequestParser.optionalTitle`).
  - Availability handled via the backend's existing `YOUTUBE_VIDEO_UNAVAILABLE` error during analyze.
- **Curation:** Kept, redesigned as a bottom "My clips" tray.
- **Layout:** Mobile-first, single column.

## Architecture

### Repo

New `web/` directory alongside `ios/` and `backend-nest/`. iOS is not deleted.

```
web/
  src/
    api/
      analyzeClient.ts   — POST /analyze SSE stream → progress callbacks + final result
      sse.ts             — reusable SSE frame parser (event:/data: line buffering)
      types.ts           — AnalyzeResponse, AnalyzeCategory, AnalyzeKeyword, AnalyzeSource,
                           ProgressUpdate, error-envelope types
      errors.ts          — error code → user-facing message map (ported from AnalyzeServiceError)
      youtube.ts         — parse videoId from URL forms, build thumbnail + timestamp URLs,
                           format seconds → m:ss
    hooks/
      useAnalyze.ts      — state machine (idle → streaming → result / error), owns the stream
      useClips.ts        — curation state: selected keywords + per-item display level
    components/          — presentational (see UI section)
    App.tsx
    main.tsx
  index.html
  package.json
  vite.config.ts
  tsconfig.json
```

### Data flow

1. User pastes a YouTube URL → `youtube.ts` parses `videoId` client-side →
   thumbnail preview renders from the derived image URL.
2. Analyze → `fetch` `POST {backendBaseURL}/analyze?stream=progress` with
   headers `Content-Type: application/json`, `Accept: text/event-stream`, body
   `{ type: "youtube", youtubeUrl }` (no `title`).
3. Read `response.body.getReader()` + `TextDecoder`, feed bytes to `sse.ts` which
   emits parsed frames `{ event, data }`.
   - `started` / `progress` / `completed` → progress UI (stage label + stepper).
   - `result` → parse into `AnalyzeResponse`, transition to result state.
   - `error` → parse `{ stage, statusCode, code, message }`, transition to error state.
4. Streaming replaces iOS's `URLSession.bytes(for:)`. Browser `ReadableStream` +
   `TextDecoder` handles chunked bytes; `sse.ts` handles line buffering and
   concatenated JSON objects in one chunk (same edge case iOS handled).

### Backend change required

Enable CORS on NestJS for the web origin (`app.enableCors(...)` in
`backend-nest/src/main.ts`). None exists today because the iOS client is native.
Allow the configured web origin(s); dev allows `http://localhost:5173` (Vite default).
This is the only backend change.

## SSE contract (reference)

Endpoint: `POST /analyze?stream=progress` (also triggered by
`Accept: text/event-stream`). Frames are `event: <name>\ndata: <json>\n\n`.

Events:
- `started` — `{ stage: "started", message }`
- `progress` — `{ stage, message }`
- `completed` — `{ stage: "completed", message }`
- `result` — the full `AnalyzeResponse` JSON
- `error` — `{ stage, statusCode, code, message }`

Actual backend `progress` stage strings, in order (from `analyze.service.ts` —
note the iOS `loadingStages` list was stale and must not be copied):

```
started
fetching_transcript
sanitizing_transcript
transcript_ready
creating_segments
chunking_topics
validating_chunks
extracting_clippings
reviewing_coverage
storing_analysis
completed
```

The stepper must not hardcode a fixed count tied to this exact list — drive it
from a known ordered list but degrade gracefully if an unknown stage arrives
(show its friendly-or-raw label, don't crash). Friendly labels map known stages
to human text (e.g. `fetching_transcript` → "Fetching transcript…",
`chunking_topics` → "Finding topics…", `extracting_clippings` → "Extracting
clips…", `storing_analysis` → "Saving…").

### Response shape

```ts
AnalyzeResponse { transcriptId, sourceType, categories, expiresInSeconds, videoId? }
AnalyzeCategory { title, keywords }
AnalyzeKeyword  { term, brief, level1, level2, level3, source }
AnalyzeSource   { type, ref }   // ref is a YouTube URL with &t=<sec>s
```

## UI / screens (mobile-first)

Single page, no routing. Column layout, `max-width: ~640px`, centered on desktop.
Four states driven by `useAnalyze`.

### Header + input (sticky top)

- "Reforge" wordmark.
- URL input + Analyze button. Kept at **top** (not a bottom-fixed bar — mobile
  browser chrome fights fixed bottom bars).
- Clear (✕) control when input is non-empty.
- Thumbnail preview card renders under the input once a `videoId` parses.
- Submit on button click or Enter.

### Idle state

Centered hint: "Paste a YouTube link to analyze it."

### Streaming state

Slim progress block (not a full-screen overlay — too heavy for web):
- Friendly current-stage label.
- Stepper (dots) filling by stage order.
- Indeterminate progress bar.

### Result state

- Categories as a **vertical accordion** (mobile-native; no horizontal-scroll chips).
  Tap a category header → expands its keyword list. One expanded at a time
  (matches iOS single-expand behavior).
- Each keyword row: `term` (bold) + `brief`, a timestamp link (`m:ss`, parsed from
  `source.ref` `&t=`, opens the YouTube URL), and an "add" affordance.
- Tapping a keyword adds it to the **"My clips" tray**.

### "My clips" tray (curation)

- Collapsible panel pinned at the bottom of the result view.
- Grouped by category title.
- Each clip item: `term` + current-level text, a "more" control stepping
  level1 → level2 → level3 in place, a timestamp link, and a remove (✕).
- Selection keyed by `${categoryTitle}::${term}`; display level defaults to 1.
- State lives in `useClips`.

### Error state

Inline message from the `errors.ts` code→message map; Analyze acts as retry.

## Error handling

Ported from iOS `AnalyzeServiceError`:

- **Non-2xx response** → parse `{ error: { code, message } }` envelope → mapped message.
- **SSE `error` event** → `{ code, message }` → same map.
- **Network / fetch throw** → generic "Couldn't reach the server."
- **Stream ended without a `result`** → "Server finished without returning data."

Code→message map covers the known codes: `YOUTUBE_VIDEO_UNAVAILABLE`,
`YOUTUBE_URL_INVALID` / `INVALID_YOUTUBE_URL`, `TRANSCRIPT_UNAVAILABLE`,
`TRANSCRIPT_PROVIDER_RATE_LIMITED`, `TRANSCRIPT_PROVIDER_ERROR` /
`TRANSCRIPT_FETCH_FAILED`, `PYTHON_*`, `TRANSCRIPT_PARSE_FAILED`, `OPENAI_*`.
Unknown codes fall back to the server `message` (or a generic line if empty).

## Config

Backend base URL from a Vite env var (`VITE_BACKEND_BASE_URL`), falling back to
`http://localhost:3000` — mirrors iOS `AppConfig`.

## Testing

Vitest (iOS had no tests, but the pure logic here is worth covering):

- `sse.ts` — frame parsing, multiline `data:`, concatenated JSON objects in one chunk.
- `youtube.ts` — videoId extraction across URL forms (`watch?v=`, `youtu.be/`,
  with extra params), `m:ss` timestamp formatting.
- `errors.ts` — code → message mapping, unknown-code fallback.
- Components: skipped for v1 (keep light).

## Out of scope (v1)

- Deployment/hosting setup (static build produced; where it's hosted is a later call).
- Removing or modifying the iOS client.
- oEmbed / title autofill / pre-analyze availability check.
- Manual (`type: "manual"`) transcript input — YouTube only for v1.
