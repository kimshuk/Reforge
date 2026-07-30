import json

import httpx
import pytest

from app.config import Settings
from app.errors import AppError
from app.llm import (
    LlmClient,
    sentence_count,
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


def test_reports_all_explanation_ladder_violations() -> None:
    with pytest.raises(AppError) as raised:
        validate_explanation_ladder(
            GOOD["title"],
            "This brief contains far too many words for a glanceable explanation today",
            "Pricing pressure affects prices. It can affect decisions.",
            "The speaker discusses pricing pressure.",
            "The speaker discusses pricing. The team responds.",
        )

    assert "Brief must contain 5-10 words" in raised.value.message
    assert "Simple explanation has 2 sentences; expected exactly 1" in raised.value.message
    assert "Contextual explanation has 1 sentence; expected 2-3" in raised.value.message
    assert "Detailed explanation has 2 sentences; expected 3-5" in raised.value.message


def test_rejects_source_ref_outside_parent_chunk() -> None:
    with pytest.raises(AppError) as raised:
        validate_candidate(GOOD, 0, ["S002", "S003"])

    assert raised.value.code == "LLM_CLIPPINGS_INVALID_SOURCE_REF"


def test_accepts_glanceable_brief_without_whitespace() -> None:
    candidate = {**GOOD, "brief": "競合他社が製品価格を引き下げている"}

    assert validate_candidate(candidate, 0, ["S001", "S002"])["brief"] == candidate["brief"]


def test_accepts_glanceable_korean_brief_with_fewer_than_five_space_delimited_words() -> None:
    candidate = {**GOOD, "brief": "AI가 시장 변동성을 유발한다"}

    assert validate_candidate(candidate, 0, ["S001", "S002"])["brief"] == candidate["brief"]


def test_still_rejects_english_brief_with_fewer_than_five_words() -> None:
    candidate = {**GOOD, "brief": "Market volatility increases quickly"}

    with pytest.raises(AppError, match="5-10 words"):
        validate_candidate(candidate, 0, ["S001", "S002"])


@pytest.mark.parametrize(
    "simple",
    [
        "The U.S. market changes quickly in this example.",
        "The value increases from 1.5 to 2.0 in this example.",
        "An e.g. marker can appear inside one valid sentence.",
    ],
)
def test_accepts_single_sentences_with_internal_periods(simple: str) -> None:
    candidate = {**GOOD, "simpleExplanation": simple}

    assert validate_candidate(candidate, 0, ["S001", "S002"])["simpleExplanation"] == simple


@pytest.mark.parametrize(
    "value",
    [
        "The speaker cites the U.S. The market falls.",
        "The speaker lists several risks, etc. The market falls.",
    ],
)
def test_counts_sentence_ending_abbreviations_as_boundaries(value: str) -> None:
    assert sentence_count(value) == 2


@pytest.mark.asyncio
async def test_retries_candidate_generation_once_with_validation_feedback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invalid = {
        **GOOD,
        "contextualExplanation": "The speaker says competitors are pushing prices down.",
    }
    responses = [
        json.dumps({"candidateClippings": [invalid]}),
        json.dumps({"candidateClippings": [GOOD]}),
    ]
    calls: list[tuple[str, str]] = []
    llm = LlmClient(Settings())

    async def generate(system: str, user: str, _options: dict, _schema: dict) -> str:
        calls.append((system, user))
        return responses.pop(0)

    monkeypatch.setattr(llm, "_generate", generate)

    candidates = await llm.generate_candidate_clippings(
        "Pricing",
        "The speaker discusses competitive pricing pressure.",
        "S001 | 00:00 | Competitors are pushing prices down.\n"
        "S002 | 00:05 | The team needs a clearer response.",
        "en",
        {"provider": "openai", "model": "gpt-4o-mini", "temperature": 0.2},
    )

    assert candidates == [GOOD]
    assert len(calls) == 2
    assert "Contextual explanation has 1 sentence; expected 2-3" in calls[1][1]
    assert calls[0][1] in calls[1][1]


@pytest.mark.asyncio
async def test_candidate_retry_feedback_includes_violations_from_every_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invalid_context = {
        **GOOD,
        "title": "Context Failure",
        "contextualExplanation": "The speaker only provides one sentence.",
    }
    invalid_detail = {
        **GOOD,
        "title": "Detail Failure",
        "detailedExplanation": "The speaker provides one point. The team responds.",
    }
    responses = [
        json.dumps({"candidateClippings": [invalid_context, invalid_detail]}),
        json.dumps({"candidateClippings": [GOOD]}),
    ]
    calls: list[str] = []
    llm = LlmClient(Settings())

    async def generate(_system: str, user: str, _options: dict, _schema: dict) -> str:
        calls.append(user)
        return responses.pop(0)

    monkeypatch.setattr(llm, "_generate", generate)

    await llm.generate_candidate_clippings(
        "Pricing",
        "The speaker discusses competitive pricing pressure.",
        "S001 | 00:00 | Competitors are pushing prices down.\n"
        "S002 | 00:05 | The team needs a clearer response.",
        "en",
        {"provider": "openai", "model": "gpt-4o-mini", "temperature": 0.2},
    )

    assert 'Candidate 0 "Context Failure"' in calls[1]
    assert "Contextual explanation has 1 sentence; expected 2-3" in calls[1]
    assert 'Candidate 1 "Detail Failure"' in calls[1]
    assert "Detailed explanation has 2 sentences; expected 3-5" in calls[1]


@pytest.mark.asyncio
async def test_retries_when_first_candidate_correction_has_a_new_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invalid_context = {
        **GOOD,
        "contextualExplanation": "The speaker says competitors are pushing prices down.",
    }
    invalid_progression = {
        **GOOD,
        "brief": (
            "Competitors consistently force every existing product price sharply "
            "downward today"
        ),
        "simpleExplanation": "Pricing pressure makes prices difficult to maintain.",
    }
    responses = [
        json.dumps({"candidateClippings": [invalid_context]}),
        json.dumps({"candidateClippings": [invalid_progression]}),
        json.dumps({"candidateClippings": [GOOD]}),
    ]
    llm = LlmClient(Settings())

    async def generate(_system: str, _user: str, _options: dict, _schema: dict) -> str:
        return responses.pop(0)

    monkeypatch.setattr(llm, "_generate", generate)

    candidates = await llm.generate_candidate_clippings(
        "Pricing",
        "The speaker discusses competitive pricing pressure.",
        "S001 | 00:00 | Competitors are pushing prices down.\n"
        "S002 | 00:05 | The team needs a clearer response.",
        "en",
        {"provider": "openai", "model": "gpt-4o-mini", "temperature": 0.2},
    )

    assert candidates == [GOOD]
    assert responses == []


@pytest.mark.asyncio
async def test_stops_after_two_invalid_candidate_corrections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invalid = {
        **GOOD,
        "contextualExplanation": "The speaker says competitors are pushing prices down.",
    }
    calls = 0
    llm = LlmClient(Settings())

    async def generate(_system: str, _user: str, _options: dict, _schema: dict) -> str:
        nonlocal calls
        calls += 1
        return json.dumps({"candidateClippings": [invalid]})

    monkeypatch.setattr(llm, "_generate", generate)

    with pytest.raises(AppError, match="Contextual explanation has 1 sentence; expected 2-3"):
        await llm.generate_candidate_clippings(
            "Pricing",
            "The speaker discusses competitive pricing pressure.",
            "S001 | 00:00 | Competitors are pushing prices down.\n"
            "S002 | 00:05 | The team needs a clearer response.",
            "en",
            {"provider": "openai", "model": "gpt-4o-mini", "temperature": 0.2},
        )

    assert calls == 3


@pytest.mark.asyncio
async def test_does_not_retry_candidate_provider_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    llm = LlmClient(Settings())

    async def generate(_system: str, _user: str, _options: dict, _schema: dict) -> str:
        nonlocal calls
        calls += 1
        raise AppError(502, "LLM_REQUEST_FAILED", "Provider unavailable")

    monkeypatch.setattr(llm, "_generate", generate)

    with pytest.raises(AppError, match="Provider unavailable"):
        await llm.generate_candidate_clippings(
            "Pricing",
            "The speaker discusses competitive pricing pressure.",
            "S001 | 00:00 | Competitors are pushing prices down.",
            "en",
            {"provider": "openai", "model": "gpt-4o-mini", "temperature": 0.2},
        )

    assert calls == 1


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
