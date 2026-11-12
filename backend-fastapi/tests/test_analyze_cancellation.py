import asyncio
import json

import pytest

import app.main as main_module
from app.database import get_db
from app.main import app


class SlowCleanupService:
    def __init__(self, events: list[str], *_args) -> None:
        self.events = events

    async def analyze(self, _body, emit):
        emit("progress", {"stage": "chunking_topics", "message": "Working"})
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            await asyncio.sleep(0.01)
            self.events.append("failure_recorded")
            raise


async def disconnect_after_first_event(events: list[str]) -> None:
    first_chunk = asyncio.Event()
    request_sent = False

    async def receive():
        nonlocal request_sent
        if not request_sent:
            request_sent = True
            return {"type": "http.request", "body": json.dumps({}).encode(), "more_body": False}
        await first_chunk.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        if message["type"] == "http.response.body" and message.get("body"):
            first_chunk.set()

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/analyze",
        "raw_path": b"/analyze",
        "query_string": b"stream=progress",
        "root_path": "",
        "headers": [(b"content-type", b"application/json")],
        "client": ("127.0.0.1", 1),
        "server": ("127.0.0.1", 3000),
    }
    await asyncio.wait_for(app(scope, receive, send), timeout=2)


@pytest.mark.asyncio
async def test_disconnect_records_failure_before_closing_db_session(monkeypatch) -> None:
    events: list[str] = []

    async def tracked_db():
        try:
            yield object()
        finally:
            events.append("db_closed")

    monkeypatch.setattr(
        main_module,
        "AnalyzeService",
        lambda *args: SlowCleanupService(events, *args),
    )
    app.dependency_overrides[get_db] = tracked_db
    try:
        await disconnect_after_first_event(events)
        await asyncio.sleep(0.05)
    finally:
        app.dependency_overrides.pop(get_db)

    assert events == ["failure_recorded", "db_closed"]
