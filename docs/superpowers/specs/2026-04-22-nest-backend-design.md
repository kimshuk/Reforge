# NestJS Backend Design

**Goal:** Replace the existing Express backend with a NestJS app that receives a YouTube URL or manual text, fetches and sanitizes the transcript, sends it to an LLM via OpenRouter, and returns structured categories with keyword drill-downs.

---

## Architecture

A single NestJS app with one feature module (`AnalyzeModule`) containing four focused services and one controller.

```
AppModule
└── AnalyzeModule
    ├── AnalyzeController        — HTTP routing, delegates to AnalyzeService
    ├── AnalyzeService           — thin orchestrator
    ├── TranscriptService        — video ID extraction, Python subprocess, sanitizer
    ├── LlmService               — prompt building, OpenRouter call, response parsing
    └── TranscriptStoreService   — in-memory UUID→transcript store with TTL
```

Config (API key, model, Python binary path) is loaded via `ConfigModule.forRoot({ isGlobal: true })` from a `.env` file. No authentication now; a NestJS Guard can be added to the controller later without touching any other layer.

---

## API Endpoints

### POST /analyze

**Request:**
```json
{ "type": "youtube", "url": "https://www.youtube.com/watch?v=...", "targetLanguage": "en" }
{ "type": "manual", "text": "raw transcript text here", "targetLanguage": "en" }
```

- `type` — required, `"youtube"` or `"manual"`
- `url` — required when `type` is `"youtube"`
- `text` — required when `type` is `"manual"`
- `targetLanguage` — optional BCP-47 code, defaults to `"en"`

**Response (200):**
```json
{
  "transcriptId": "550e8400-e29b-41d4-a716-446655440000",
  "sourceType": "youtube",
  "categories": [
    {
      "title": "Category Title",
      "keywords": [
        {
          "term": "keyword phrase",
          "brief": "short hint",
          "level1": "direct factual statement",
          "level2": "expanded with transcript detail",
          "level3": "most detailed reconstruction",
          "source": { "type": "youtube", "ref": "https://youtube.com/watch?v=...&t=120s" }
        }
      ]
    }
  ],
  "expiresInSeconds": 3600
}
```

For `manual` type, `source.ref` is a verbatim excerpt from the text instead of a URL.

### GET /transcript/:id

Returns the stored transcript text by UUID.

**Response (200):**
```json
{ "transcriptId": "550e8400-...", "text": "S001 | 00:00 | ..." }
```

**Response (404):** standard error envelope (expired or never existed)

### Error Envelope

All errors use the same shape:
```json
{ "error": { "code": "ERROR_CODE", "message": "Human-readable description" } }
```

A global `HttpExceptionFilter` in `main.ts` converts all `HttpException` instances to this shape.

---

## Error Codes

| Code | HTTP | Cause |
|------|------|-------|
| `INVALID_REQUEST` | 400 | Malformed or missing request body fields |
| `INVALID_YOUTUBE_URL` | 400 | URL not parseable or not a recognized YouTube format |
| `TRANSCRIPT_UNAVAILABLE` | 502 | Video exists but has no transcript |
| `TRANSCRIPT_TOO_SHORT` | 502 | Transcript too short to analyze (<80 chars) |
| `PYTHON_RUNTIME_ERROR` | 502 | Python subprocess failed to start |
| `PYTHON_DEPENDENCY_MISSING` | 500 | `youtube-transcript-api` not installed |
| `LLM_REQUEST_FAILED` | 502 | OpenRouter unreachable or network error |
| `LLM_INVALID_RESPONSE` | 502 | Model returned malformed or empty JSON |
| `LLM_INVALID_SOURCE_REF` | 502 | Model returned a timestamp not present in the transcript |
| `TRANSCRIPT_NOT_FOUND` | 404 | UUID expired or never existed |

---

## Data Flow

### YouTube path

1. Validate request body (class-validator + `ValidationPipe`)
2. `TranscriptService.fetchAndSanitize(url)`
   - Extract video ID from URL
   - Spawn `python3 scripts/fetch_transcript.py <videoId>`
   - Parse stdout JSON → raw snippets
   - Sanitize: strip noise, normalize text, build timed segments
   - Return `{ videoId, llmTranscriptText, segmentIndex }`
3. `TranscriptStoreService.set(llmTranscriptText)` → returns `{ transcriptId, expiresInSeconds }`
4. `LlmService.analyze({ transcriptText, segmentIndex, youtubeUrl, targetLanguage })`
   - Build system + user prompt with segment format `S### | MM:SS | text`
   - POST to OpenRouter with JSON schema response format
   - Parse response JSON
   - Resolve each keyword's `source.ref` timestamp → full YouTube URL with `?t=Ns`
   - Return `{ sourceType, categories }`
5. Combine and return response

### Manual path

1. Validate request body
2. Skip transcript fetch — use `text` directly as `transcriptText`
3. `TranscriptStoreService.set(text)` → `{ transcriptId, expiresInSeconds }`
4. `LlmService.analyze({ transcriptText, segmentIndex: [], youtubeUrl: '', targetLanguage })`
   - Same prompt structure, manual mode
   - `source.ref` is a verbatim excerpt, no timestamp resolution
5. Combine and return response

---

## File Structure

```
backend-nest/
  scripts/
    fetch_transcript.py           — Python transcript fetcher (copied from old backend)
  src/
    analyze/
      dto/
        analyze.dto.ts            — AnalyzeDto: { type, url?, text?, targetLanguage? }
      transcript/
        transcript.service.ts     — video ID extraction, Python spawn, sanitizer
        transcript.service.spec.ts
      llm/
        llm.service.ts            — prompt builder, OpenRouter fetch, source resolution
        llm.service.spec.ts
      store/
        transcript-store.service.ts     — in-memory Map with TTL, UUID generation
        transcript-store.service.spec.ts
      analyze.controller.ts       — POST /analyze, GET /transcript/:id
      analyze.controller.spec.ts
      analyze.service.ts          — orchestrator
      analyze.service.spec.ts
      analyze.module.ts           — wires all providers
    filters/
      http-exception.filter.ts    — formats all errors to { error: { code, message } }
    app.module.ts                 — ConfigModule + AnalyzeModule
    main.ts                       — global ValidationPipe + global exception filter
  .env                            — OPENROUTER_API_KEY, OPENROUTER_MODEL, PYTHON_BIN
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENROUTER_API_KEY` | Yes | — | OpenRouter API key |
| `OPENROUTER_MODEL` | No | `openai/gpt-4o-mini` | Model identifier passed to OpenRouter |
| `PYTHON_BIN` | No | `python3` | Python executable path |

---

## Testing Strategy

Each service unit-tested in isolation with Vitest:

- **TranscriptService** — mock `child_process.spawn`; test video ID extraction (watch URL, short URL, youtu.be, invalid), sanitizer output, and all error exit paths
- **LlmService** — mock global `fetch`; test prompt structure, JSON parsing, source ref resolution, non-ok response handling
- **TranscriptStoreService** — test set/get lifecycle, TTL expiry using fake timers, UUID format
- **AnalyzeService** — mock all three services; verify correct delegation for both YouTube and manual paths
- **AnalyzeController** — mock `AnalyzeService`; verify request routing, 404 on missing transcript, error envelope shape

No end-to-end tests initially. After each service is implemented, smoke test manually with `curl`.

---

## Out of Scope (for now)

- Authentication / authorization
- Rate limiting
- Persistent storage (database)
- Manual text input beyond raw string (no file upload)
