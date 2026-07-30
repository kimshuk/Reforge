import json
from typing import Any

import pytest

from app.config import Settings
from app.enrichment import (
    EnrichmentContext,
    EnrichmentPlan,
    OccurrenceEnrichment,
    ResearchEvidence,
    ResearchSource,
)
from app.enrichment_prompts import (
    ENRICHMENT_PLAN_SCHEMA,
    ENRICHMENT_REVIEW_SCHEMA,
    ENRICHMENT_SYNTHESIS_SCHEMA,
)
from app.errors import AppError
from app.llm import LlmClient

OPENAI_OPTIONS = {
    "provider": "openai",
    "model": "gpt-4o-mini",
    "temperature": 0.2,
}

GOOD = {
    "brief": "Competitors are pushing product prices downward",
    "simpleExplanation": "Pricing pressure means outside forces make prices harder to maintain.",
    "contextualExplanation": "The speaker says competitors are pushing prices down. The team therefore needs a clearer response.",
    "detailedExplanation": "The speaker claims competitors are pushing prices down. Buyers compare the options mentioned in the chunk directly. That mechanism makes the current approach harder to defend. The team therefore needs a clearer pricing response.",
}


def context(keyword_id: str = "K001", **overrides: Any) -> EnrichmentContext:
    values = {
        "keyword_id": keyword_id,
        "term": "Pricing Pressure",
        "kind": "claim",
        "brief": GOOD["brief"],
        "simple_explanation": GOOD["simpleExplanation"],
        "chunk_title": "Competitive pricing",
        "chunk_summary": "The speaker discusses competitors lowering prices.",
        "source_excerpts": ("Competitors are pushing prices down.",),
        "transcript_level2": GOOD["contextualExplanation"],
        "transcript_level3": GOOD["detailedExplanation"],
        "video_topic_outline": ("Competition", "Pricing"),
    }
    values.update(overrides)
    return EnrichmentContext(**values)


def plan_payload(keyword_id: str = "K001", **overrides: Any) -> dict[str, Any]:
    values = {
        "keywordId": keyword_id,
        "level2": GOOD["contextualExplanation"],
        "level3": GOOD["detailedExplanation"],
        "needsExternalResearch": False,
        "researchQuestion": "",
        "preferredSourceClass": "none",
    }
    values.update(overrides)
    return values


def evidence() -> ResearchEvidence:
    return ResearchEvidence(
        summary="Official product documentation supports the terminology.",
        sources=(
            ResearchSource(
                citation_id="C1",
                title="Source C1",
                url="https://example.com/c1",
                supporting_text="Supporting evidence for the enrichment.",
            ),
        ),
    )


def synthesis_payload(**overrides: Any) -> dict[str, Any]:
    values = {
        "keywordId": "K001",
        "level2": GOOD["contextualExplanation"],
        "level3": GOOD["detailedExplanation"],
        "level2CitationIds": [],
        "level3CitationIds": ["C1"],
    }
    values.update(overrides)
    return values


@pytest.mark.asyncio
async def test_planner_returns_one_decision_per_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm = LlmClient(Settings())
    calls: list[str] = []

    async def generate(
        _system: str, _user: str, _options: dict[str, Any], schema: dict[str, Any]
    ) -> str:
        calls.append(schema["name"])
        return json.dumps({"plans": [plan_payload("K001")]})

    monkeypatch.setattr(llm, "_generate", generate)

    plans = await llm.plan_explanation_enrichment(
        [context("K001")], "en", OPENAI_OPTIONS
    )

    assert plans[0].keyword_id == "K001"
    assert calls == [ENRICHMENT_PLAN_SCHEMA["name"]]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"plans": [plan_payload("K999")]},
        {"plans": []},
    ],
)
async def test_planner_rejects_unknown_or_missing_occurrence_ids(
    monkeypatch: pytest.MonkeyPatch, payload: dict[str, Any]
) -> None:
    llm = LlmClient(Settings())

    async def generate(
        _system: str, _user: str, _options: dict[str, Any], _schema: dict[str, Any]
    ) -> str:
        return json.dumps(payload)

    monkeypatch.setattr(llm, "_generate", generate)

    with pytest.raises(AppError) as raised:
        await llm.plan_explanation_enrichment([context()], "en", OPENAI_OPTIONS)

    assert raised.value.code == "LLM_ENRICHMENT_PLAN_INVALID_JSON"


@pytest.mark.asyncio
async def test_synthesis_uses_schema_and_rejects_invalid_citation_mappings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm = LlmClient(Settings())
    calls: list[str] = []

    async def generate(
        _system: str, _user: str, _options: dict[str, Any], schema: dict[str, Any]
    ) -> str:
        calls.append(schema["name"])
        return json.dumps(synthesis_payload(level3CitationIds=["C999"]))

    monkeypatch.setattr(llm, "_generate", generate)

    with pytest.raises(AppError) as raised:
        await llm.synthesize_explanation_enrichment(
            context(),
            llm_plan(),
            evidence(),
            "en",
            OPENAI_OPTIONS,
        )

    assert raised.value.code == "LLM_ENRICHMENT_SYNTHESIS_INVALID_JSON"
    assert calls == [ENRICHMENT_SYNTHESIS_SCHEMA["name"]]


@pytest.mark.asyncio
async def test_review_returns_false_for_rejection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm = LlmClient(Settings())
    calls: list[str] = []

    async def generate(
        _system: str, _user: str, _options: dict[str, Any], schema: dict[str, Any]
    ) -> str:
        calls.append(schema["name"])
        return json.dumps({"approved": False, "reasonCode": "unsupported_claim"})

    monkeypatch.setattr(llm, "_generate", generate)

    approved = await llm.review_explanation_enrichment(
        context(),
        occurrence_enrichment(),
        evidence(),
        "en",
        OPENAI_OPTIONS,
    )

    assert approved is False
    assert calls == [ENRICHMENT_REVIEW_SCHEMA["name"]]


@pytest.mark.asyncio
async def test_provider_errors_propagate_from_enrichment_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm = LlmClient(Settings())

    async def generate(
        _system: str, _user: str, _options: dict[str, Any], _schema: dict[str, Any]
    ) -> str:
        raise AppError(502, "LLM_REQUEST_FAILED", "Provider unavailable")

    monkeypatch.setattr(llm, "_generate", generate)

    with pytest.raises(AppError) as raised:
        await llm.plan_explanation_enrichment([context()], "en", OPENAI_OPTIONS)

    assert raised.value.code == "LLM_REQUEST_FAILED"


def llm_plan() -> EnrichmentPlan:
    return EnrichmentPlan(
        keyword_id="K001",
        level2=GOOD["contextualExplanation"],
        level3=GOOD["detailedExplanation"],
        needs_external_research=False,
        research_question="",
        preferred_source_class="none",
    )


def occurrence_enrichment() -> OccurrenceEnrichment:
    return OccurrenceEnrichment(
        keyword_id="K001",
        level2=GOOD["contextualExplanation"],
        level3=GOOD["detailedExplanation"],
        level3_citation_ids=("C1",),
        external_sources=evidence().sources,
    )
