# Reforge Nest Backend

NestJS backend for transcript ingestion and category analysis.

## Docker

From the repository root:

```bash
docker compose up
```

This starts:

- `backend-nest` on `http://localhost:3000`
- Postgres on `localhost:5432`
- Redis on `localhost:6379`

The backend image includes Node, Python, and `youtube-transcript-api` for
transcript fetching.

Docker Compose sets `TYPEORM_MIGRATIONS_RUN=true` so local database migrations
run when the backend starts.

## Environment

```env
PORT=3000
PYTHON_BIN=python3
DATABASE_URL=postgres://reforge:reforge@postgres:5432/reforge
REDIS_URL=redis://redis:6379
TYPEORM_MIGRATIONS_RUN=true
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_TEMPERATURE=0.2
LLM_MAX_OUTPUT_TOKENS=3000
ALLOW_ANALYZE_LLM_OVERRIDES=false
OPENAI_API_KEY=
GEMINI_API_KEY=
ANTHROPIC_API_KEY=
```

`LLM_PROVIDER`, `LLM_MODEL`, `LLM_TEMPERATURE`, and `LLM_MAX_OUTPUT_TOKENS`
control the production `/analyze` model. Request-level model overrides are
disabled by default; set `ALLOW_ANALYZE_LLM_OVERRIDES=true` only for internal
development or eval work.

## API

- `GET /health`
- `POST /analyze`
- `POST /analyze?stream=progress` or `Accept: text/event-stream`
- `GET /transcript/:transcriptId`

## LLM Summary Test CLI

Use the CLI to compare providers and model settings without running the HTTP
server.

Manual transcript:

```bash
npm run llm:test-summary -- \
  --type manual \
  --file ./sample-transcript.txt \
  --provider openai \
  --model gpt-4o-mini \
  --temperature 0.2 \
  --max-output-tokens 1200
```

YouTube transcript:

```bash
npm run llm:test-summary -- \
  --type youtube \
  --youtube-url "https://www.youtube.com/watch?v=..." \
  --provider gemini \
  --model gemini-1.5-pro \
  --temperature 0.2
```

Save runs for comparison:

```bash
npm run llm:test-summary -- --type manual --file ./sample.txt --provider claude --model claude-3-5-sonnet-latest > claude-summary.json
```

The command returns JSON with the effective LLM settings, a concise summary, and
timestamped moments. Add `--include-raw-text` to include the provider's raw text
response for debugging.
