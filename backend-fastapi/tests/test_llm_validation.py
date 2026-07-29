import httpx
import pytest

from app.config import Settings
from app.errors import AppError
from app.llm import (
    LlmClient,
    validate_candidate,
    validate_category_grouping,
    validate_explanation_ladder,
)

GOOD = {
    "kind": "claim",
    "title": "Pricing Pressure",
    "text": "Competitors are forcing the team to revisit pricing.",
    "brief": "Competitors are pushing product prices downward",
    "simpleExplanation": "Pricing pressure means outside forces make prices harder to maintain.",
    "contextualExplanation": "The speaker says competitors are pushing prices down. The team therefore needs a clearer response.",
    "detailedExplanation": "The speaker claims competitors are pushing prices down. Buyers compare the options mentioned in the chunk directly. That mechanism makes the current approach harder to defend. The team therefore needs a clearer pricing response.",
    "signalLevel": "high",
    "sourceRefs": [
        {
            "startSegmentId": "S001",
            "endSegmentId": "S002",
            "timestamp": "00:00",
            "text": "Competitors are pushing prices down.",
        }
    ],
}


def test_accepts_progressive_explanation_ladder_and_chunk_refs() -> None:
    result = validate_candidate(GOOD, 0, ["S001", "S002"])

    assert result["title"] == "Pricing Pressure"
    assert result["sourceRefs"][0]["endSegmentId"] == "S002"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", "x" * 61),
        ("brief", "Too short"),
        ("contextualExplanation", "Only one contextual sentence."),
        ("detailedExplanation", "Only one. Only two."),
    ],
)
def test_rejects_invalid_ladder_shape(field: str, value: str) -> None:
    candidate = {**GOOD, field: value}

    with pytest.raises(AppError) as raised:
        validate_candidate(candidate, 0, ["S001", "S002"])

    assert raised.value.code == "LLM_CLIPPINGS_INVALID_JSON"


def test_rejects_duplicate_levels() -> None:
    with pytest.raises(AppError, match="must not be duplicates"):
        validate_explanation_ladder(
            GOOD["title"],
            GOOD["brief"],
            GOOD["simpleExplanation"],
            GOOD["simpleExplanation"],
            GOOD["detailedExplanation"],
        )


def test_rejects_source_ref_outside_parent_chunk() -> None:
    with pytest.raises(AppError) as raised:
        validate_candidate(GOOD, 0, ["S002", "S003"])

    assert raised.value.code == "LLM_CLIPPINGS_INVALID_SOURCE_REF"


def test_accepts_glanceable_brief_without_whitespace() -> None:
    candidate = {**GOOD, "brief": "競合他社が製品価格を引き下げている"}

    assert validate_candidate(candidate, 0, ["S001", "S002"])["brief"] == candidate["brief"]


def test_accepts_complete_occurrence_category_partition_with_duplicate_terms() -> None:
    result = validate_category_grouping(
        {
            "categories": [
                {"title": "OpenAI", "keywordIds": ["K001", "K002"]},
                {"title": "Google", "keywordIds": ["K003"]},
            ]
        },
        ["K001", "K002", "K003"],
    )

    assert result == [
        {"title": "OpenAI", "keywordIds": ["K001", "K002"]},
        {"title": "Google", "keywordIds": ["K003"]},
    ]


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"categories": [{"title": "OpenAI", "keywordIds": ["K001"]}]}, "exactly once"),
        ({"categories": [{"title": "OpenAI", "keywordIds": ["K001", "K999", "K002"]}]}, "unknown"),
        (
            {
                "categories": [
                    {"title": "OpenAI", "keywordIds": ["K001", "K002"]},
                    {"title": "Tools", "keywordIds": ["K002"]},
                ]
            },
            "exactly once",
        ),
        (
            {
                "categories": [
                    {"title": "Open AI", "keywordIds": ["K001"]},
                    {"title": " open   ai ", "keywordIds": ["K002"]},
                ]
            },
            "titles",
        ),
        ({"categories": [{"title": "OpenAI", "keywordIds": []}]}, "non-empty"),
        ({"categories": [{"title": "x" * 81, "keywordIds": ["K001", "K002"]}]}, "titles"),
    ],
)
def test_rejects_invalid_occurrence_category_partition(payload: dict, message: str) -> None:
    with pytest.raises(AppError, match=message):
        validate_category_grouping(payload, ["K001", "K002"])


@pytest.mark.asyncio
async def test_maps_failed_openai_response_to_request_failed() -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, json={"status": "failed"})
    )
    async with httpx.AsyncClient(transport=transport) as client:
        llm = LlmClient(Settings(openai_api_key="test-key"), client)
        with pytest.raises(AppError) as raised:
            await llm.generate_topic_chunks(
                "S001 | 00:00 | Transcript text",
                "en",
                {
                    "provider": "openai",
                    "model": "gpt-4o-mini",
                    "temperature": 0.2,
                    "maxOutputTokens": 3000,
                },
            )

    assert raised.value.code == "LLM_REQUEST_FAILED"
