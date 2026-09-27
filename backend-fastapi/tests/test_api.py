import json

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.errors import AppError
from app.main import app
from app.schemas import YoutubeTranscriptResponse

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


def test_transcript_openapi_documents_request_and_response() -> None:
    document = client.get("/openapi.json").json()
    operation = document["paths"]["/youtube/transcript"]["post"]

    request_schema = operation["requestBody"]["content"]["application/json"]["schema"]
    response_schema = operation["responses"]["200"]["content"]["application/json"][
        "schema"
    ]

    assert request_schema == {"$ref": "#/components/schemas/YoutubeTranscriptRequest"}
    assert response_schema == {"$ref": "#/components/schemas/YoutubeTranscriptResponse"}


def transcript_response(text: str) -> YoutubeTranscriptResponse:
    return YoutubeTranscriptResponse(
        transcriptId="11111111-1111-4111-8111-111111111111",
        videoId="dQw4w9WgXcQ",
        canonicalYoutubeUrl="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        transcriptText=text,
        languageCode="en",
        language="English",
        isGenerated=False,
    )


def install_transcript_service(monkeypatch, result):
    class StubTranscriptService:
        def __init__(self, _store) -> None:
            pass

        async def ingest(self, _youtube_url, _title):
            if isinstance(result, Exception):
                raise result
            return result

    monkeypatch.setattr(main_module, "YoutubeTranscriptIngestionService", StubTranscriptService)


def test_transcript_endpoint_accepts_65_to_79_character_source(monkeypatch) -> None:
    text = "x" * 70
    install_transcript_service(monkeypatch, transcript_response(text))

    response = client.post(
        "/youtube/transcript",
        json={"youtubeUrl": "https://youtu.be/dQw4w9WgXcQ"},
    )

    assert response.status_code == 200
    assert response.json()["transcriptText"] == text


def test_transcript_endpoint_accepts_noise_only_nonempty_source(monkeypatch) -> None:
    install_transcript_service(monkeypatch, transcript_response("[Music]"))

    response = client.post(
        "/youtube/transcript",
        json={"youtubeUrl": "https://youtu.be/dQw4w9WgXcQ"},
    )

    assert response.status_code == 200
    assert response.json()["transcriptText"] == "[Music]"


@pytest.mark.parametrize(
    ("code", "status"),
    [
        ("EMPTY_TRANSCRIPT", 502),
        ("TRANSCRIPT_UNAVAILABLE", 502),
        ("TRANSCRIPT_FETCH_FAILED", 502),
        ("INVALID_YOUTUBE_URL", 400),
    ],
)
def test_transcript_endpoint_returns_existing_error_envelope(
    monkeypatch, code: str, status: int
) -> None:
    install_transcript_service(monkeypatch, AppError(status, code, "safe message"))

    response = client.post(
        "/youtube/transcript",
        json={"youtubeUrl": "https://youtu.be/dQw4w9WgXcQ"},
    )

    assert response.status_code == status
    assert response.json() == {"error": {"code": code, "message": "safe message"}}


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        ([], "INVALID_REQUEST"),
        ({}, "INVALID_YOUTUBE_URL"),
        ({"youtubeUrl": "   "}, "INVALID_YOUTUBE_URL"),
        (
            {"youtubeUrl": "https://youtu.be/dQw4w9WgXcQ", "title": "   "},
            "INVALID_TITLE",
        ),
        (
            {"youtubeUrl": "https://youtu.be/dQw4w9WgXcQ", "unknown": True},
            "INVALID_REQUEST",
        ),
        (
            {"youtubeUrl": "https://youtu.be/dQw4w9WgXcQ", "": True},
            "INVALID_REQUEST",
        ),
    ],
)
def test_transcript_endpoint_validates_request_fields(payload, code: str) -> None:
    response = client.post("/youtube/transcript", json=payload)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == code


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
    assert definitions["ExternalKeywordSource"]["properties"]["citationId"]
    assert keyword_schema["properties"]["level2CitationIds"]
    assert keyword_schema["properties"]["level3CitationIds"]
    assert keyword_schema["properties"]["externalSources"]["items"] == {
        "$ref": "#/components/schemas/ExternalKeywordSource"
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
