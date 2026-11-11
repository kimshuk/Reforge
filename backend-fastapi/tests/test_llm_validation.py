import json

import httpx
import pytest

from app.config import Settings
from app.errors import AppError
from app.llm import (
    LlmClient,
    normalize_candidate_sentences,
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
        "U.S.-China diplomatic communications mean leaders talk to manage their relationship.",
        "Reducing exposure to U.S. Treasuries means Chinese banks hold fewer government bonds.",
        "The U.S. Treasury issues government bonds to fund public spending.",
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
        "The speaker cites the U.S. Treasury. The market falls.",
        "U.S.-China talks continue. The market falls.",
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


async def generate_candidates_from(
    monkeypatch: pytest.MonkeyPatch, responses: list[list[dict]]
) -> tuple[list[dict], list[str]]:
    users: list[str] = []
    llm = LlmClient(Settings())

    async def generate(_system: str, user: str, _options: dict, _schema: dict) -> str:
        users.append(user)
        return json.dumps({"candidateClippings": responses[len(users) - 1]})

    monkeypatch.setattr(llm, "_generate", generate)
    candidates = await llm.generate_candidate_clippings(
        "Pricing",
        "The speaker discusses competitive pricing pressure.",
        "S001 | 00:00 | Competitors are pushing prices down.\n"
        "S002 | 00:05 | The team needs a clearer response.",
        "en",
        {"provider": "openai", "model": "gpt-4o-mini", "temperature": 0.2},
    )
    return candidates, users


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid",
    [
        {**GOOD, "title": "Short Brief", "brief": "Too short"},
        {**GOOD, "title": "Single Item", "contextualExplanation": ["Only one sentence here."]},
        {
            **GOOD,
            "title": "Bad Source",
            "sourceRefs": [{**GOOD["sourceRefs"][0], "startSegmentId": "S999"}],
        },
    ],
    ids=["ladder", "normalization", "source-ref"],
)
async def test_final_attempt_keeps_valid_candidates_and_drops_invalid_ones(
    monkeypatch: pytest.MonkeyPatch, invalid: dict
) -> None:
    candidates, users = await generate_candidates_from(
        monkeypatch, [[invalid, GOOD]] * 3
    )

    assert len(users) == 3
    assert [candidate["title"] for candidate in candidates] == [GOOD["title"]]


@pytest.mark.asyncio
async def test_earlier_attempts_retry_instead_of_dropping_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invalid = {**GOOD, "title": "Repaired Later", "brief": "Too short"}
    repaired = {**GOOD, "title": "Repaired Later"}

    candidates, users = await generate_candidates_from(
        monkeypatch, [[invalid, GOOD], [repaired, GOOD]]
    )

    assert len(users) == 2
    assert [candidate["title"] for candidate in candidates] == ["Repaired Later", GOOD["title"]]


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


def test_sentence_arrays_preserve_public_string_fields() -> None:
    candidate = {
        **GOOD,
        "contextualExplanation": [
            "The speaker says competitors are pushing prices down.",
            "The team therefore needs a clearer response.",
        ],
        "detailedExplanation": [
            "The speaker claims competitors are pushing prices down.",
            "Buyers compare the options mentioned in the chunk directly.",
            "That mechanism makes the current approach harder to defend.",
            "The team therefore needs a clearer pricing response.",
        ],
    }
    normalized = normalize_candidate_sentences([candidate])
    assert validate_candidate(normalized[0], 0, ["S001", "S002"]) == GOOD
    assert isinstance(candidate["contextualExplanation"], list)


@pytest.mark.parametrize("items", [
    ["Only one sentence."],
    ["First sentence. Hidden second sentence.", "Third sentence."],
    ["", "Another sentence."],
    [None, "Another sentence."],
    ["x" * 421, "Another sentence."],
])
def test_rejects_invalid_sentence_arrays(items) -> None:
    with pytest.raises(AppError):
        normalize_candidate_sentences([{**GOOD, "contextualExplanation": items}])


@pytest.mark.asyncio
async def test_generation_normalizes_structured_sentence_arrays(monkeypatch) -> None:
    llm = LlmClient(Settings())
    async def generate(_system, _user, _options, schema):
        properties = schema["schema"]["properties"]["candidateClippings"]["items"]["properties"]
        assert properties["contextualExplanation"]["minItems"] == 2
        assert properties["detailedExplanation"]["minItems"] == 3
        return json.dumps({"candidateClippings": [{
            **GOOD,
            "contextualExplanation": ["The speaker says competitors are pushing prices down.", "The team therefore needs a clearer response."],
            "detailedExplanation": ["The speaker claims competitors are pushing prices down.", "Buyers compare the options mentioned in the chunk directly.", "That mechanism makes the current approach harder to defend.", "The team therefore needs a clearer pricing response."],
        }]})
    monkeypatch.setattr(llm, "_generate", generate)
    assert await llm.generate_candidate_clippings(
        "Pricing", "Pricing pressure", "S001 | 00:00 | Prices drop.\nS002 | 00:05 | Team responds.", "en", {}
    ) == [GOOD]


@pytest.mark.parametrize("value", [
    "In the U.S., seasonal factors cause companies to raise wages or prices.",
    "The speaker describes the U.S.: inflation affects markets.",
    "The speaker describes the U.S.; inflation affects markets.",
])
def test_abbreviation_followed_by_continuation_punctuation_is_not_a_boundary(value):
    assert sentence_count(value) == 1


def test_sentence_array_accepts_abbreviation_followed_by_comma() -> None:
    candidate = {**GOOD, "contextualExplanation": [
        "In the U.S., competitive pressure makes product prices difficult to maintain.",
        "The speaker connects that pressure to the team needing a clearer response.",
    ]}
    normalized = normalize_candidate_sentences([candidate])
    assert validate_candidate(normalized[0], 0, ["S001", "S002"])


@pytest.mark.asyncio
async def test_category_grouping_repairs_missing_occurrence_ids(monkeypatch) -> None:
    llm = LlmClient(Settings())
    calls = []
    responses = [
        {"categories": [{"title": "Pricing", "keywordIds": ["K001"]}]},
        {"categories": [{"title": "Pricing", "keywordIds": ["K001", "K002"]}]},
    ]
    async def generate(_system, user, _options, _schema):
        calls.append(user)
        return json.dumps(responses.pop(0))
    monkeypatch.setattr(llm, "_generate", generate)
    result = await llm.generate_keyword_categories([{"keywordId": "K001"}, {"keywordId": "K002"}], "en", {})
    assert result[0]["keywordIds"] == ["K001", "K002"]
    assert len(calls) == 2
    assert 'Required IDs: ["K001", "K002"]' in calls[1]


@pytest.mark.asyncio
async def test_category_grouping_stops_after_three_invalid_responses(monkeypatch) -> None:
    llm = LlmClient(Settings())
    calls = 0
    async def generate(*_args):
        nonlocal calls
        calls += 1
        return json.dumps({"categories": []})
    monkeypatch.setattr(llm, "_generate", generate)
    with pytest.raises(AppError):
        await llm.generate_keyword_categories([{"keywordId": "K001"}], "en", {})
    assert calls == 3


def grouping_occurrences(count: int) -> list[dict]:
    return [
        {"keywordId": f"K{index:03d}", "term": f"Term {index}"}
        for index in range(1, count + 1)
    ]


def fake_grouping_llm(monkeypatch, responses: list[dict]) -> tuple[LlmClient, list[str]]:
    llm = LlmClient(Settings())
    calls: list[str] = []

    async def generate(_system, user, _options, _schema):
        calls.append(user)
        return json.dumps(responses[len(calls) - 1])

    monkeypatch.setattr(llm, "_generate", generate)
    return llm, calls


def assigned_ids(categories: list[dict]) -> list[str]:
    return [item for category in categories for item in category["keywordIds"]]


def test_exactly_once_error_names_missing_and_duplicated_ids() -> None:
    with pytest.raises(AppError) as error:
        validate_category_grouping(
            {
                "categories": [
                    {"title": "Pricing", "keywordIds": ["K001", "K002"]},
                    {"title": "Tools", "keywordIds": ["K002"]},
                ]
            },
            ["K001", "K002", "K003"],
        )
    assert "missing: K003" in error.value.message
    assert "duplicated: K002" in error.value.message


@pytest.mark.asyncio
async def test_category_grouping_correction_names_offending_ids(monkeypatch) -> None:
    occurrences = grouping_occurrences(3)
    llm, calls = fake_grouping_llm(
        monkeypatch,
        [
            {"categories": [{"title": "Pricing", "keywordIds": ["K001", "K002"]}]},
            {"categories": [{"title": "Pricing", "keywordIds": ["K001", "K002", "K003"]}]},
        ],
    )
    await llm.generate_keyword_categories(occurrences, "en", {})
    assert "missing: K003" in calls[1]


@pytest.mark.asyncio
async def test_large_grouping_survives_three_incomplete_partitions(monkeypatch) -> None:
    occurrences = grouping_occurrences(52)
    ids = [item["keywordId"] for item in occurrences]
    # Same shape on every attempt: K051/K052 omitted, K001 repeated, as a model
    # that cannot track a 52-item partition would return.
    response = {
        "categories": [
            {"title": "Pricing", "keywordIds": ids[:30]},
            {"title": "Tools", "keywordIds": ["K001", *ids[30:50]]},
            {"title": "Only Duplicates", "keywordIds": ["K002"]},
        ]
    }
    llm, calls = fake_grouping_llm(monkeypatch, [response] * 3)

    result = await llm.generate_keyword_categories(occurrences, "en", {})

    assert len(calls) == 3
    assert sorted(assigned_ids(result)) == ids
    assert validate_category_grouping({"categories": result}, ids) == result
    assert [category["title"] for category in result] == [
        "Pricing", "Tools", "Term 51", "Term 52",
    ]


@pytest.mark.asyncio
async def test_repaired_singleton_joins_category_with_matching_title(monkeypatch) -> None:
    occurrences = [
        {"keywordId": "K001", "term": "Pricing"},
        {"keywordId": "K002", "term": " pricing "},
        {"keywordId": "K003", "term": "Pricing"},
    ]
    response = {"categories": [{"title": "Pricing", "keywordIds": ["K001"]}]}
    llm, _calls = fake_grouping_llm(monkeypatch, [response] * 3)

    result = await llm.generate_keyword_categories(occurrences, "en", {})

    assert result == [{"title": "Pricing", "keywordIds": ["K001", "K002", "K003"]}]


@pytest.mark.asyncio
async def test_final_attempt_does_not_repair_unknown_ids(monkeypatch) -> None:
    response = {"categories": [{"title": "Pricing", "keywordIds": ["K001", "K999"]}]}
    llm, calls = fake_grouping_llm(monkeypatch, [response] * 3)

    with pytest.raises(AppError, match="unknown occurrence ID"):
        await llm.generate_keyword_categories(grouping_occurrences(2), "en", {})
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_category_grouping_does_not_retry_provider_errors(monkeypatch) -> None:
    llm = LlmClient(Settings())
    calls = 0
    async def generate(*_args):
        nonlocal calls
        calls += 1
        raise AppError(502, "LLM_QUOTA_OR_RATE_LIMIT", "Rate limit")
    monkeypatch.setattr(llm, "_generate", generate)
    with pytest.raises(AppError, match="Rate limit"):
        await llm.generate_keyword_categories([{"keywordId": "K001"}], "en", {})
    assert calls == 1


@pytest.mark.parametrize(("field", "limit"), [
    ("contextualExplanation", 420),
    ("detailedExplanation", 700),
])
def test_largest_schema_sentence_arrays_fit_joined_character_limit(field, limit) -> None:
    from app.prompts import CANDIDATE_CLIPPING_SCHEMA

    properties = CANDIDATE_CLIPPING_SCHEMA["schema"]["properties"]["candidateClippings"]["items"]["properties"]
    schema = properties[field]
    # Exercise the maximum sentence count AND item length, including joining spaces.
    sentence = "A" + "b" * (schema["items"]["maxLength"] - 2) + "."
    items = [sentence] * schema["maxItems"]
    joined = " ".join(items)
    assert len(joined) <= limit
    normalized = normalize_candidate_sentences([{**GOOD, field: items}])
    assert normalized[0][field] == joined


@pytest.mark.asyncio
async def test_generation_repairs_joined_character_overflow(monkeypatch) -> None:
    llm = LlmClient(Settings())
    responses = [
        {**GOOD, "contextualExplanation": ["A" + "b" * 208 + ".", "C" + "d" * 208 + "."]},
        GOOD,
    ]
    users = []

    async def generate(_system, user, _options, _schema):
        users.append(user)
        return json.dumps({"candidateClippings": [responses.pop(0)]})

    monkeypatch.setattr(llm, "_generate", generate)
    assert await llm.generate_candidate_clippings(
        "Pricing", "Pricing pressure", "S001 | 00:00 | Prices drop.\nS002 | 00:05 | Team responds.", "en", {}
    ) == [GOOD]
    assert len(users) == 2
    assert "joined contextualExplanation exceeds 420 characters" in users[1]
