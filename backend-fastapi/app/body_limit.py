import json
from collections.abc import Awaitable, Callable
from typing import Any

MAX_ANALYZE_BODY_BYTES = 1024 * 1024


class AnalyzeBodyLimitMiddleware:
    def __init__(self, app: Callable[..., Awaitable[None]]) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Callable[..., Awaitable[dict[str, Any]]], send: Callable[..., Awaitable[None]]) -> None:
        if scope.get("type") != "http" or scope.get("method") != "POST" or scope.get("path") != "/analyze":
            await self.app(scope, receive, send)
            return
        messages: list[dict[str, Any]] = []
        total = 0
        while True:
            message = await receive()
            total += len(message.get("body", b""))
            if total > MAX_ANALYZE_BODY_BYTES:
                await self._reject(send)
                return
            messages.append(message)
            if not message.get("more_body", False):
                break

        async def replay() -> dict[str, Any]:
            return messages.pop(0) if messages else await receive()

        await self.app(scope, replay, send)

    async def _reject(self, send: Callable[..., Awaitable[None]]) -> None:
        body = json.dumps(
            {"error": {"code": "INTERNAL_SERVER_ERROR", "message": "Request body is too large"}}
        ).encode()
        await send({"type": "http.response.start", "status": 413, "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})
