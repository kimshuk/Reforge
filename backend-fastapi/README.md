# Reforge FastAPI Backend

This service replaces `backend-nest` while preserving the public API and PostgreSQL schema.

## Local development

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
cp .env.example .env
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload --port 3000
```

Run tests with:

```bash
.venv/bin/pytest
```

The service exposes:

- `POST /analyze`, with JSON or SSE progress responses
- `GET /transcript/{transcriptId}`
- `GET /health`

`level1`, `level2`, and `level3` remain compatibility response fields. Internally they are generated and validated as `simpleExplanation`, `contextualExplanation`, and `detailedExplanation` before persistence.

## Rollback

The baseline migration preserves the legacy Nest table names, columns, indexes, and UUID defaults. To switch the local stack back:

```bash
docker compose stop backend-fastapi
docker compose --profile rollback up -d backend-nest
curl http://localhost:3000/health
```

To return to FastAPI, stop `backend-nest` and run `docker compose up -d backend-fastapi`.
