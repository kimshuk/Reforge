---
title: Keep JSON ingestion endpoints inside the shared body limit
date: 2026-09-28
area: backend
status: verified
---

## Problem

The backend limited `POST /analyze` request bodies to 1 MiB, but the later `POST /youtube/transcript` endpoint was not included. FastAPI therefore parsed an oversized transcript-ingestion JSON body and passed its unbounded `title` to the service layer.

## Mistake and why it failed

`backend-fastapi/app/body_limit.py` encoded one endpoint path in both the middleware name and its condition. Adding another JSON ingestion endpoint did not naturally extend that condition. Existing tests only proved the original `/analyze` behavior, so the new route could bypass the intended server boundary.

## Verified approach

The middleware is now named `RequestBodyLimitMiddleware` and checks membership in `LIMITED_POST_PATHS`, currently `/analyze` and `/youtube/transcript`. `backend-fastapi/tests/test_api.py` sends bodies larger than 1 MiB to both endpoints and requires HTTP 413 with the existing error envelope.

The transcript test failed with HTTP 502 before the change and passed with HTTP 413 afterward. The complete backend suite passed with 170 tests, 1 skipped, and Ruff passed with `--no-cache`.

## Prevention

When adding a POST endpoint that parses user-controlled JSON, decide explicitly whether it belongs in `LIMITED_POST_PATHS` and add an oversized-body regression test. Do not infer coverage from another endpoint using the same FastAPI application.
