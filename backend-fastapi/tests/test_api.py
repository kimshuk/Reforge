import json

from fastapi.testclient import TestClient

import app.main as main_module
from app.main import app

client = TestClient(app)


def test_analyze_openapi_documents_body_and_stream_parameters() -> None:
    operation = client.get("/openapi.json").json()["paths"]["/analyze"]["post"]

    body = operation["requestBody"]["content"]["application/json"]
    assert body["schema"]["properties"]["type"]
    assert body["examples"]["manual"]["value"]["type"] == "manual"
    assert body["examples"]["youtube"]["value"]["type"] == "youtube"

    parameters = {(item["in"], item["name"].lower()) for item in operation["parameters"]}
    assert ("query", "stream") in parameters
    assert ("header", "accept") in parameters


def test_analyze_openapi_documents_semantic_category_response() -> None:
    document = client.get("/openapi.json").json()
    operation = document["paths"]["/analyze"]["post"]
    success = operation["responses"]["200"]["content"]

    result_schema = success["application/json"]["schema"]
    assert result_schema == {"$ref": "#/components/schemas/AnalyzeResult"}
    definitions = document["components"]["schemas"]
    category_schema = definitions["AnalyzeCategory"]
    assert category_schema["properties"]["categoryId"]
    assert category_schema["properties"]["keywords"]["items"] == {
        "$ref": "#/components/schemas/AnalyzeKeyword"
    }
    keyword_schema = definitions["AnalyzeKeyword"]
    assert keyword_schema["properties"]["candidateClippingId"]
    assert keyword_schema["properties"]["source"] == {
        "$ref": "#/components/schemas/KeywordSource"
    }
    assert keyword_schema["properties"]["sources"]["items"] == {
        "$ref": "#/components/schemas/KeywordSource"
    }
    assert success["text/event-stream"]["examples"]["result"]["summary"]


def test_rejects_non_object_analyze_body_with_compatible_error() -> None:
    response = client.post("/analyze", json=[])

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "INVALID_REQUEST",
            "message": "Request body must be a JSON object",
        }
    }


def test_rejects_invalid_transcript_uuid() -> None:
    response = client.get("/transcript/not-a-uuid")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_TRANSCRIPT_ID"


def test_streams_validation_errors_after_sse_is_requested() -> None:
    response = client.post(
        "/analyze?stream=progress",
        headers={"Accept": "text/event-stream"},
        json=[],
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: error" in response.text
    assert (
        'data: {"stage": "error", "statusCode": 400, "code": "INVALID_REQUEST", '
        '"message": "Request body must be a JSON object"}' in response.text
    )


def test_rejects_analyze_body_over_one_megabyte() -> None:
    response = client.post(
        "/analyze",
        content=b'{"type":"manual","text":"' + b"x" * (1024 * 1024) + b'"}',
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413
    assert response.json()["error"]["message"] == "Request body is too large"


def test_wraps_framework_404_in_compatible_envelope() -> None:
    response = client.get("/missing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_sse_negotiation_is_case_insensitive() -> None:
    response = client.post(
        "/analyze?stream=PrOgReSs",
        headers={"Accept": "Text/Event-Stream"},
        json=[],
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")


def test_json_and_sse_result_payloads_are_identical(monkeypatch) -> None:
    expected = {
        "transcriptId": "transcript-id",
        "sourceType": "youtube",
        "categories": [],
        "expiresInSeconds": 1800,
        "llm": {"provider": "openai", "model": "test", "temperature": 0.2},
        "videoId": "video-id",
    }

    class StubAnalyzeService:
        def __init__(self, *_args) -> None:
            pass

        async def analyze(self, _body, emit=None):
            if emit:
                emit("progress", {"stage": "grouping_keywords"})
            return expected

    monkeypatch.setattr(main_module, "AnalyzeService", StubAnalyzeService)

    json_response = client.post(
        "/analyze",
        json={"type": "youtube", "youtubeUrl": "https://youtube.com/watch?v=test"},
    )
    stream_response = client.post(
        "/analyze?stream=progress",
        headers={"Accept": "text/event-stream"},
        json={"type": "youtube", "youtubeUrl": "https://youtube.com/watch?v=test"},
    )

    result_data = next(
        json.loads(line.removeprefix("data: "))
        for event, line in zip(stream_response.text.splitlines(), stream_response.text.splitlines()[1:])
        if event == "event: result" and line.startswith("data: ")
    )
    assert json_response.json() == expected
    assert result_data == expected
