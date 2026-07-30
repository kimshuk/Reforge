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

The PostgreSQL migration contract test is opt-in because it downgrades and re-upgrades its target database. Point it only at a disposable database:

```bash
TEST_DATABASE_URL=postgresql+psycopg://reforge:reforge@localhost:5432/reforge \
  .venv/bin/pytest tests/test_postgres_category_contract.py
```

The service exposes:

- `POST /analyze`, with JSON or SSE progress responses
- `GET /transcript/{transcriptId}`
- `GET /health`

`level1`, `level2`, and `level3` remain compatibility response fields. Internally they are generated and validated as `simpleExplanation`, `contextualExplanation`, and `detailedExplanation` before persistence.

Topic chunks are internal, time-bounded extraction units. The response instead contains semantic categories with no category-level timestamp. Each keyword is a contextual occurrence with its own `candidateClippingId`, explanation ladder, and source:

```json
{
  "categoryId": "d34174eb-26c9-48e1-9739-c602d2649d32",
  "title": "OpenAI",
  "keywords": [
    {
      "candidateClippingId": "744fa8cf-9ef9-45b9-8472-500588026ce2",
      "term": "Codex",
      "brief": "Autonomous coding tool introduced here",
      "level1": "Codex is a tool that performs coding tasks.",
      "level2": "The speaker introduces Codex as an autonomous coding tool. They describe the work it can perform.",
      "level3": "The speaker introduces Codex as an autonomous coding tool. They claim it can perform concrete coding work. The mechanism is autonomous task execution. The example establishes why the tool matters in this section.",
      "source": {"type": "youtube", "ref": "https://www.youtube.com/watch?v=example&t=46s"},
      "sources": [{"type": "youtube", "ref": "https://www.youtube.com/watch?v=example&t=46s"}]
    }
  ]
}
```

Equal `term` values at different transcript ranges remain separate keyword records. Only accidental records with the same normalized term and the same resolved segment range are collapsed. `source` is the occurrence's primary reference. `sources` is an occurrence-local ordered list whose first item is the primary source; any remaining items support that same contextual occurrence and never represent unrelated appearances of the term.

## Manual JSON and SSE verification

Use a video that discusses the same keyword in meaningfully different sections. The example below uses the Korean-language test video from the API walkthrough:

```bash
REQUEST='{"type":"youtube","youtubeUrl":"https://youtu.be/DGd5nbYiAis","targetLanguage":"ko"}'

curl -sS http://localhost:3000/analyze \
  -H 'Accept: application/json' \
  -H 'Content-Type: application/json' \
  -d "$REQUEST" > /tmp/reforge-analysis.json

curl -sS 'http://localhost:3000/analyze?stream=progress' \
  -H 'Accept: text/event-stream' \
  -H 'Content-Type: application/json' \
  -d "$REQUEST" > /tmp/reforge-analysis.sse

sed -n '/^event: result$/{n;s/^data: //;p;}' /tmp/reforge-analysis.sse \
  > /tmp/reforge-analysis-sse-result.json
```

Both JSON files must expose the same result shape. IDs differ because these are separate analysis runs:

```bash
jq -s -e '
  all(.[];
    . as $result |
    ($result.categories | length > 0) and
    ([$result.categories[] | select((.keywords | length) == 0)] | length == 0) and
    ([$result.categories[].keywords[] | has("candidateClippingId") and
      (.source.ref | test("[?&]t=[0-9]+s")) and
      (.source == .sources[0])] | all)
  )
' /tmp/reforge-analysis.json /tmp/reforge-analysis-sse-result.json

jq '[paths(scalars) | map(if type == "number" then "[]" else . end)] | unique' \
  /tmp/reforge-analysis.json > /tmp/reforge-json-shape
jq '[paths(scalars) | map(if type == "number" then "[]" else . end)] | unique' \
  /tmp/reforge-analysis-sse-result.json > /tmp/reforge-sse-shape
diff -u /tmp/reforge-json-shape /tmp/reforge-sse-shape
```

To inspect repeated display terms, group by normalized term. Any repeated term must retain distinct occurrence IDs, explanations, and source timestamps:

```bash
jq '
  [.categories[].keywords[]]
  | group_by(.term | ascii_downcase)
  | map(select(length > 1)
      | map({term, candidateClippingId, level2, level3, source}))
' /tmp/reforge-analysis.json

jq -e '
  [.categories[].keywords[] | .term |= ascii_downcase]
  | group_by(.term)
  | any(length > 1)
' /tmp/reforge-analysis.json
```

Existing analysis runs are not backfilled. Rerun analysis to obtain semantic categories. The NestJS rollback service remains available but returns its legacy response shape.

## Rollback

The baseline migration preserves the legacy Nest table names, columns, indexes, and UUID defaults. To switch the local stack back:

```bash
docker compose stop backend-fastapi
docker compose --profile rollback up -d backend-nest
curl http://localhost:3000/health
```

To return to FastAPI, stop `backend-nest` and run `docker compose up -d backend-fastapi`.
