from typing import Any

import pytest

from app.enrichment import (
    EnrichmentContext,
    ResearchEvidence,
    ResearchSource,
    validate_plan_payload,
    validate_synthesis_payload,
)
from app.enrichment_prompts import (
    ENRICHMENT_PLAN_SCHEMA,
    ENRICHMENT_REVIEW_SCHEMA,
    ENRICHMENT_SYNTHESIS_SCHEMA,
    enrichment_plan_prompt,
    enrichment_review_prompt,
    enrichment_synthesis_prompt,
)
from app.errors import AppError

GOOD = {
    "brief": "Competitors are pushing product prices downward",
    "simpleExplanation": "Pricing pressure means outside forces make prices harder to maintain.",
    "contextualExplanation": "The speaker says competitors are pushing prices down. The team therefore needs a clearer response.",
    "detailedExplanation": "The speaker claims competitors are pushing prices down. Buyers compare the options mentioned in the chunk directly. That mechanism makes the current approach harder to defend. The team therefore needs a clearer pricing response.",
}


def context(keyword_id: str = "K001", term: str = "Pricing Pressure", **overrides: Any) -> EnrichmentContext:
    values = {
        "keyword_id": keyword_id,
        "term": term,
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


def plan(
    keyword_id: str = "K001",
    *,
    level2: str = GOOD["contextualExplanation"],
    level3: str = GOOD["detailedExplanation"],
    needs_research: bool = False,
    research_question: str = "",
    preferred_source_class: Any = "none",
    **overrides: Any,
) -> dict[str, Any]:
    values = {
        "keywordId": keyword_id,
        "level2": level2,
        "level3": level3,
        "needsExternalResearch": needs_research,
        "researchQuestion": research_question,
        "preferredSourceClass": preferred_source_class,
    }
    values.update(overrides)
    return values


def evidence(source_ids: list[str] | None = None, **overrides: Any) -> ResearchEvidence:
    source_ids = source_ids or ["C1"]
    values = {
        "summary": "Official product documentation supports the terminology.",
        "sources": tuple(
            ResearchSource(
                citation_id=citation_id,
                title=f"Source {citation_id}",
                url=f"https://example.com/{citation_id.lower()}",
                supporting_text="Supporting evidence for the enrichment.",
            )
            for citation_id in source_ids
        ),
    }
    values.update(overrides)
    return ResearchEvidence(**values)


def synthesis(
    *,
    keyword_id: str = "K001",
    level2: str = GOOD["contextualExplanation"],
    level3: str = GOOD["detailedExplanation"],
    level2_citation_ids: list[str] | None = None,
    level3_citation_ids: list[str] | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    values = {
        "keywordId": keyword_id,
        "level2": level2,
        "level3": level3,
        "level2CitationIds": level2_citation_ids if level2_citation_ids is not None else [],
        "level3CitationIds": level3_citation_ids if level3_citation_ids is not None else ["C1"],
    }
    values.update(overrides)
    return values


def test_plan_assigns_every_occurrence_once() -> None:
    contexts = [context("K001", "Codex"), context("K002", "Codex")]

    plans = validate_plan_payload(
        {
            "plans": [
                plan("K001", needs_research=False),
                plan(
                    "K002",
                    needs_research=True,
                    research_question="What mechanism is described?",
                    preferred_source_class="reference",
                ),
            ]
        },
        contexts,
    )

    assert [item.keyword_id for item in plans] == ["K001", "K002"]


def test_plan_keeps_same_term_contexts_independent() -> None:
    contexts = [context("K001", "Codex"), context("K002", "Codex")]

    plans = validate_plan_payload(
        {"plans": [plan("K001"), plan("K002")]}, contexts
    )

    assert [item.keyword_id for item in plans] == ["K001", "K002"]


def test_plan_rejects_unknown_duplicate_and_missing_occurrence_ids() -> None:
    with pytest.raises(AppError, match="occurrence"):
        validate_plan_payload(
            {"plans": [plan("K001"), plan("K001"), plan("K999")]},
            [context("K001"), context("K002")],
        )


def test_plan_aggregates_invalid_source_class_type() -> None:
    with pytest.raises(AppError, match="preferredSourceClass"):
        validate_plan_payload(
            {"plans": [plan(preferred_source_class=[])]},
            [context()],
        )


@pytest.mark.parametrize("citation_ids", [["C9"], ["C1", "C1"]])
def test_synthesis_rejects_unknown_or_duplicate_citations(citation_ids: list[str]) -> None:
    with pytest.raises(AppError, match="citation"):
        validate_synthesis_payload(
            synthesis(level3_citation_ids=citation_ids),
            context("K001", "Codex"),
            evidence(source_ids=["C1"]),
        )


def test_synthesis_cannot_change_level1_or_occurrence_identity() -> None:
    with pytest.raises(AppError, match="immutable"):
        validate_synthesis_payload(
            {**synthesis(), "keywordId": "K999", "simpleExplanation": "Changed."},
            context("K001", "Codex"),
            evidence(),
        )


@pytest.mark.parametrize(
    "url",
    [
        "/relative",
        "ftp://example.com/source",
        "https:///missing-host",
        "https://:443/path",
        "https://user@/path",
        "https://[::1",
        "https://example.com:bad/path",
    ],
)
def test_synthesis_requires_absolute_http_urls(url: str) -> None:
    invalid_evidence = evidence(
        sources=(
            ResearchSource("C1", "Source C1", url, "Supporting evidence."),
        )
    )

    with pytest.raises(AppError, match="URL"):
        validate_synthesis_payload(synthesis(), context(), invalid_evidence)


def test_synthesis_rejects_noncanonical_source_citation_ids() -> None:
    invalid_evidence = evidence(
        sources=(
            ResearchSource(
                " C1 ",
                "Source C1",
                "https://example.com/c1",
                "Supporting evidence.",
            ),
        )
    )

    with pytest.raises(AppError, match="canonical"):
        validate_synthesis_payload(synthesis(), context(), invalid_evidence)


def test_synthesis_retains_sources_for_valid_citation_mappings() -> None:
    result = validate_synthesis_payload(synthesis(), context(), evidence())

    assert result.level3_citation_ids == ("C1",)
    assert [source.citation_id for source in result.external_sources] == ["C1"]


def test_synthesis_requires_unique_source_ids_and_at_most_three_sources() -> None:
    duplicate_evidence = evidence(source_ids=["C1", "C1"])
    oversized_evidence = evidence(source_ids=["C1", "C2", "C3", "C4"])

    with pytest.raises(AppError, match="citation"):
        validate_synthesis_payload(synthesis(), context(), duplicate_evidence)
    with pytest.raises(AppError, match="at most three"):
        validate_synthesis_payload(synthesis(), context(), oversized_evidence)


def test_synthesis_enforces_ladder_sentence_limits() -> None:
    with pytest.raises(AppError, match="Contextual explanation has 1 sentence"):
        validate_synthesis_payload(
            synthesis(level2="Only one sentence."), context(), evidence()
        )


def test_synthesis_discards_evidence_that_is_not_cited() -> None:
    result = validate_synthesis_payload(
        synthesis(level2_citation_ids=["C2"], level3_citation_ids=[]),
        context(),
        evidence(source_ids=["C1", "C2", "C3"]),
    )

    assert result.level2_citation_ids == ("C2",)
    assert [source.citation_id for source in result.external_sources] == ["C2"]


def test_synthesis_accepts_transcript_only_enrichment_without_evidence() -> None:
    result = validate_synthesis_payload(
        synthesis(level3_citation_ids=[]),
        context(),
        ResearchEvidence(summary="", sources=()),
    )

    assert result.external_sources == ()


def test_prompt_contracts_include_examples_and_immutable_fallback_rules() -> None:
    plan_system, plan_user = enrichment_plan_prompt([context()], "en")
    synthesis_system, synthesis_user = enrichment_synthesis_prompt(
        context(),
        validate_plan_payload({"plans": [plan()]}, [context()])[0],
        evidence(),
        "en",
    )
    review_system, review_user = enrichment_review_prompt(
        context(), validate_synthesis_payload(synthesis(), context(), evidence()), evidence(), "en"
    )

    assert {"plans"} == set(ENRICHMENT_PLAN_SCHEMA["schema"]["required"])
    assert ENRICHMENT_SYNTHESIS_SCHEMA["strict"] is True
    assert ENRICHMENT_REVIEW_SCHEMA["strict"] is True
    for prompt in (plan_system, synthesis_system, review_system):
        assert "Good example" in prompt
        assert "Bad example" in prompt
        assert "immutable" in prompt
        assert "disambiguation only" in prompt
        assert "fallback" in prompt
    assert "K001" in plan_user
    assert "C1" in synthesis_user
    assert "C1" in review_user
