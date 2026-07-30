import asyncio
import json
import logging
from contextlib import asynccontextmanager, suppress
from uuid import UUID

import httpx
import redis.asyncio as redis
from fastapi import Depends, FastAPI, Header, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis import AnalyzeService
from app.body_limit import AnalyzeBodyLimitMiddleware
from app.config import get_settings
from app.database import get_db
from app.errors import AppError, register_error_handlers
from app.llm import LlmClient
from app.schemas import AnalyzeRequest, AnalyzeResult
from app.store import TranscriptStore, transcript_expiry

settings = get_settings()
logger = logging.getLogger("reforge")

ANALYZE_REQUEST_BODY = {
    "required": True,
    "content": {
        "application/json": {
            "schema": AnalyzeRequest.model_json_schema(),
            "examples": {
                "manual": {
                    "summary": "Analyze supplied text",
                    "value": {
                        "type": "manual",
                        "title": "Semantic contracts",
                        "targetLanguage": "en",
                        "text": (
                            "A semantic contract defines what each response field means. "
                            "Each explanation level adds context and detail while staying "
                            "grounded in the original source."
                        ),
                    },
                },
                "youtube": {
                    "summary": "Analyze a YouTube transcript",
                    "value": {
                        "type": "youtube",
                        "youtubeUrl": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                        "targetLanguage": "en",
                    },
                },
            },
        }
    },
}

ANALYZE_RESPONSES = {
    200: {
        "description": "Completed analysis JSON or Server-Sent Event stream.",
        "content": {
            "application/json": {"schema": AnalyzeResult.model_json_schema()},
            "text/event-stream": {
                "examples": {
                    "progress": {
                        "summary": "Progress event",
                        "value": "event: progress\ndata: {\"stage\":\"chunking_topics\"}\n\n",
                    },
                    "result": {
                        "summary": "Result event containing the AnalyzeResult payload",
                        "value": "event: result\ndata: {\"transcriptId\":\"...\",\"categories\":[]}\n\n",
                    },
                    "error": {
                        "summary": "Safe error event",
                        "value": "event: error\ndata: {\"code\":\"INVALID_REQUEST\"}\n\n",
                    },
                }
            },
        },
    }
}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _app.state.http_client = httpx.AsyncClient(timeout=120)
    yield
    await _app.state.http_client.aclose()


app = FastAPI(title="Reforge Backend", lifespan=lifespan)
app.add_middleware(AnalyzeBodyLimitMiddleware)
register_error_handlers(app)


@app.middleware("http")
async def request_logging(request: Request, call_next):
    request_id = request.headers.get("x-request-id")
    response = await call_next(request)
    if request_id:
        response.headers["x-request-id"] = request_id
    logger.info("request", extra={"method": request.method, "path": request.url.path, "status": response.status_code})
    return response


@app.get("/health")
async def health(db: AsyncSession = Depends(get_db)) -> dict:
    checks = {"backend": True, "postgres": False, "redis": False, "python": True}
    try:
        await db.execute(text("SELECT 1"))
        checks["postgres"] = True
    except Exception:
        pass
    client = redis.from_url(settings.redis_url)
    try:
        checks["redis"] = bool(await client.ping())
    except Exception:
        pass
    finally:
        await client.aclose()
    return {"ok": all(checks.values()), "checks": checks}


@app.get("/transcript/{transcript_id}")
async def get_transcript(transcript_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        parsed_id = UUID(transcript_id, version=4)
    except ValueError as error:
        raise AppError(400, "INVALID_TRANSCRIPT_ID", "transcriptId must be a valid UUID v4") from error
    if str(parsed_id) != transcript_id.lower():
        raise AppError(400, "INVALID_TRANSCRIPT_ID", "transcriptId must be a valid UUID v4")
    transcript = await TranscriptStore(db).get_transcript(parsed_id)
    if transcript is None:
        raise AppError(404, "TRANSCRIPT_NOT_FOUND", "transcriptId not found or expired")
    created_at, expires_at = transcript_expiry(transcript)
    return {
        "transcriptId": transcript_id,
        "videoId": transcript.video_id,
        "createdAt": created_at,
        "expiresAt": expires_at,
        "transcriptText": transcript.transcript_text,
    }


@app.post(
    "/analyze",
    openapi_extra={"requestBody": ANALYZE_REQUEST_BODY},
    responses=ANALYZE_RESPONSES,
)
async def analyze(
    request: Request,
    stream: str | None = Query(
        default=None,
        description="Set to 'progress' to receive Server-Sent Events.",
    ),
    accept: str | None = Header(
        default=None,
        alias="Accept",
        description="Use 'text/event-stream' to receive Server-Sent Events.",
    ),
    db: AsyncSession = Depends(get_db),
):
    try:
        body = await request.json()
    except json.JSONDecodeError as error:
        raise AppError(400, "INVALID_REQUEST", "Request body must be valid JSON") from error
    service = AnalyzeService(
        TranscriptStore(db),
        LlmClient(settings, getattr(request.app.state, "http_client", None)),
        settings,
    )
    wants_stream = "text/event-stream" in (accept or "").lower() or (stream or "").lower() == "progress"
    if not wants_stream:
        return await service.analyze(body)

    queue: asyncio.Queue[tuple[str, dict] | None] = asyncio.Queue()

    def emit(event: str, payload: dict) -> None:
        queue.put_nowait((event, payload))

    async def run() -> None:
        try:
            result = await service.analyze(body, emit)
            emit("result", result)
        except AppError as error:
            emit("error", {"stage": "error", "statusCode": error.status_code, "code": error.code, "message": error.message})
        except Exception:
            logger.exception("Streaming analysis failed")
            emit("error", {"stage": "error", "statusCode": 500, "code": "INTERNAL_SERVER_ERROR", "message": "Unexpected server error"})
        finally:
            queue.put_nowait(None)

    async def stream():
        task = asyncio.create_task(run())
        try:
            while (item := await queue.get()) is not None:
                event, payload = item
                yield f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
        finally:
            if not task.done():
                task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
