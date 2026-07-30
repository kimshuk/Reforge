import asyncio
import logging
from collections.abc import Iterable
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
from app.errors import AppError
from app.explanation_enrichment import ExplanationEnricher

OPENAI_OPTIONS = {
    "provider": "openai",
    "model": "gpt-4o-mini",
    "temperature": 0.2,
}

LEVEL2 = (
    "The speaker introduces Codex as a coding tool. "
    "It is presented as useful for delegated tasks."
)
LEVEL3 = (
    "The speaker introduces Codex as a coding tool. "
    "It can take delegated tasks from a user. "
    "That changes how the speaker frames software work. "
    "The example focuses on coding tasks."
)
PLANNED_LEVEL2 = (
    "The speaker describes Codex as an autonomous coding tool. "
    "It is connected to delegated software tasks in this section."
)
PLANNED_LEVEL3 = (
    "The speaker describes Codex as an autonomous coding tool. "
    "A user delegates a software task for the tool to complete. "
    "This mechanism changes the role of the developer in the workflow. "
    "The example remains focused on the coding work discussed here."
)


def context(keyword_id: str = "K001", **overrides: Any) -> EnrichmentContext:
    values: dict[str, Any] = {
        "keyword_id": keyword_id,
        "term": "Codex",
        "kind": "entity",
        "brief": "An autonomous coding tool from OpenAI",
        "simple_explanation": "Codex is an AI system that helps people write software.",
        "chunk_title": "Coding agents",
        "chunk_summary": "The speaker introduces Codex as an autonomous coding tool.",
        "source_excerpts": ("Codex can handle delegated coding tasks.",),
        "transcript_level2": LEVEL2,
        "transcript_level3": LEVEL3,
        "video_topic_outline": ("AI coding tools",),
    }
    values.update(overrides)
    return EnrichmentContext(**values)


def plan(
    keyword_id: str = "K001", *, needs_research: bool = True
) -> EnrichmentPlan:
    return EnrichmentPlan(
        keyword_id=keyword_id,
        level2=PLANNED_LEVEL2,
        level3=PLANNED_LEVEL3,
        needs_external_research=needs_research,
        research_question=(
            "What does official documentation say about delegated coding tasks?"
            if needs_research
            else ""
        ),
        preferred_source_class="official" if needs_research else "none",
    )


def evidence(keyword_id: str = "K001") -> ResearchEvidence:
    return ResearchEvidence(
        summary="Official documentation supports delegated coding tasks.",
        sources=(
            ResearchSource(
                citation_id="C1",
                title=f"Documentation for {keyword_id}",
                url=f"https://example.com/{keyword_id.lower()}",
                supporting_text="The documentation describes delegated coding tasks.",
            ),
        ),
    )


def synthesized(
    keyword_id: str, research_evidence: ResearchEvidence
) -> OccurrenceEnrichment:
    citation_ids = tuple(source.citation_id for source in research_evidence.sources)
    return OccurrenceEnrichment(
        keyword_id=keyword_id,
        level2=PLANNED_LEVEL2,
        level3=PLANNED_LEVEL3,
        level2_citation_ids=citation_ids,
        level3_citation_ids=citation_ids,
        external_sources=research_evidence.sources,
    )


class FakeLlm:
    def __init__(
        self,
        *,
        plans: list[EnrichmentPlan] | None = None,
        planner_error: BaseException | None = None,
        synthesis_errors: dict[str, BaseException] | None = None,
        review_results: Iterable[bool] = (True,),
    ) -> None:
        self.plans = plans
        self.planner_error = planner_error
        self.synthesis_errors = synthesis_errors or {}
        self.review_results = iter(review_results)
        self.planner_calls: list[tuple[tuple[str, ...], str]] = []
        self.synthesis_calls: list[tuple[str, ResearchEvidence]] = []
        self.review_calls: list[tuple[str, ResearchEvidence]] = []

    async def plan_explanation_enrichment(
        self,
        contexts: list[EnrichmentContext],
        target_language: str,
        _options: dict[str, Any],
    ) -> list[EnrichmentPlan]:
        self.planner_calls.append(
            (tuple(item.keyword_id for item in contexts), target_language)
        )
        if self.planner_error is not None:
            raise self.planner_error
        if self.plans is not None:
            return self.plans
        return [plan(item.keyword_id) for item in contexts]

    async def synthesize_explanation_enrichment(
        self,
        item: EnrichmentContext,
        _plan: EnrichmentPlan,
        research_evidence: ResearchEvidence,
        _target_language: str,
        _options: dict[str, Any],
    ) -> OccurrenceEnrichment:
        self.synthesis_calls.append((item.keyword_id, research_evidence))
        error = self.synthesis_errors.get(item.keyword_id)
        if error is not None:
            raise error
        return synthesized(item.keyword_id, research_evidence)

    async def review_explanation_enrichment(
        self,
        item: EnrichmentContext,
        _enrichment: OccurrenceEnrichment,
        research_evidence: ResearchEvidence,
        _target_language: str,
        _options: dict[str, Any],
    ) -> bool:
        self.review_calls.append((item.keyword_id, research_evidence))
        return next(self.review_results, True)


class FakeSearch:
    def __init__(
        self,
        *,
        search_error: BaseException | None = None,
        empty_ids: set[str] | None = None,
        delay: float = 0,
    ) -> None:
        self.search_error = search_error
        self.empty_ids = empty_ids or set()
        self.delay = delay
        self.calls: list[str] = []
        self.active_calls = 0
        self.max_active_calls = 0

    async def research_occurrence(
        self,
        item: EnrichmentContext,
        _plan: EnrichmentPlan,
        _options: dict[str, Any],
    ) -> ResearchEvidence:
        self.calls.append(item.keyword_id)
        self.active_calls += 1
        self.max_active_calls = max(self.max_active_calls, self.active_calls)
        try:
            if self.delay:
                await asyncio.sleep(self.delay)
            if self.search_error is not None:
                raise self.search_error
            if item.keyword_id in self.empty_ids:
                return ResearchEvidence(summary="No cited support", sources=())
            return evidence(item.keyword_id)
        finally:
            self.active_calls -= 1


def enricher_with(
    *,
    plans: list[EnrichmentPlan] | None = None,
    planner_error: BaseException | None = None,
    search_error: BaseException | None = None,
    synthesis_errors: dict[str, BaseException] | None = None,
    review_results: Iterable[bool] = (True,),
    empty_ids: set[str] | None = None,
    delay: float = 0,
    settings: Settings | None = None,
) -> ExplanationEnricher:
    llm = FakeLlm(
        plans=plans,
        planner_error=planner_error,
        synthesis_errors=synthesis_errors,
        review_results=review_results,
    )
    search = FakeSearch(
        search_error=search_error,
        empty_ids=empty_ids,
        delay=delay,
    )
    enricher = ExplanationEnricher(
        llm=llm,
        search=search,
        settings=settings
        or Settings(
            explanation_enrichment_enabled=True,
            explanation_enrichment_max_concurrency=3,
            openai_api_key="test-key",
        ),
    )
    return enricher


@pytest.mark.asyncio
async def test_skips_search_when_planner_finds_no_gap() -> None:
    enricher = enricher_with(plans=[plan("K001", needs_research=False)])

    result = await enricher.enrich([context("K001")], "en", OPENAI_OPTIONS)

    assert result["K001"].external_sources == ()
    assert enricher.search.calls == []
    assert enricher.llm.review_calls[0][1] == ResearchEvidence(summary="", sources=())


@pytest.mark.asyncio
async def test_search_failure_falls_back_without_raising() -> None:
    enricher = enricher_with(
        search_error=AppError(502, "LLM_REQUEST_FAILED", "failed")
    )

    result = await enricher.enrich([context("K001")], "en", OPENAI_OPTIONS)

    assert result["K001"].level2 == context("K001").transcript_level2


@pytest.mark.asyncio
async def test_duplicate_terms_are_enriched_by_occurrence_id() -> None:
    enricher = enricher_with()

    result = await enricher.enrich(
        [context("K001", term="Codex"), context("K007", term="Codex")],
        "en",
        OPENAI_OPTIONS,
    )

    assert set(result) == {"K001", "K007"}
    assert result["K001"].external_sources != result["K007"].external_sources


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("settings", "options"),
    [
        (Settings(explanation_enrichment_enabled=False), OPENAI_OPTIONS),
        (
            Settings(explanation_enrichment_enabled=True),
            {**OPENAI_OPTIONS, "provider": "gemini"},
        ),
    ],
)
async def test_disabled_or_non_openai_enrichment_makes_no_network_calls(
    settings: Settings, options: dict[str, Any]
) -> None:
    enricher = enricher_with(settings=settings)

    result = await enricher.enrich([context()], "en", options)

    assert result["K001"].level2 == LEVEL2
    assert enricher.llm.planner_calls == []
    assert enricher.search.calls == []


@pytest.mark.asyncio
async def test_empty_contexts_make_no_network_calls() -> None:
    enricher = enricher_with()

    assert await enricher.enrich([], "en", OPENAI_OPTIONS) == {}
    assert enricher.llm.planner_calls == []
    assert enricher.search.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "plans",
    [
        [plan("K001")],
        [plan("K001"), plan("K001")],
        [plan("K001"), plan("K999")],
    ],
)
async def test_invalid_plan_partition_falls_back_for_the_complete_chunk(
    plans: list[EnrichmentPlan],
) -> None:
    enricher = enricher_with(plans=plans)
    contexts = [context("K001"), context("K007")]

    result = await enricher.enrich(contexts, "en", OPENAI_OPTIONS)

    assert {key: item.level2 for key, item in result.items()} == {
        "K001": LEVEL2,
        "K007": LEVEL2,
    }
    assert enricher.search.calls == []


@pytest.mark.asyncio
async def test_planner_only_rewrite_is_reviewed_and_accepted() -> None:
    enricher = enricher_with(
        plans=[plan("K001", needs_research=False)], review_results=[True]
    )

    result = await enricher.enrich([context()], "en", OPENAI_OPTIONS)

    assert result["K001"].level2 == PLANNED_LEVEL2
    assert result["K001"].external_sources == ()
    assert len(enricher.llm.review_calls) == 1


@pytest.mark.asyncio
async def test_planner_only_rewrite_rejection_keeps_original_fallback() -> None:
    enricher = enricher_with(
        plans=[plan("K001", needs_research=False)], review_results=[False]
    )

    result = await enricher.enrich([context()], "en", OPENAI_OPTIONS)

    assert result["K001"].level2 == LEVEL2


@pytest.mark.asyncio
async def test_rejected_cited_review_gets_one_correction_attempt() -> None:
    enricher = enricher_with(review_results=[True, False, True])

    result = await enricher.enrich([context()], "en", OPENAI_OPTIONS)

    assert result["K001"].external_sources == evidence().sources
    assert len(enricher.llm.synthesis_calls) == 2
    assert len(enricher.llm.review_calls) == 3


@pytest.mark.asyncio
async def test_second_review_rejection_falls_back() -> None:
    enricher = enricher_with(review_results=[True, False, False])

    result = await enricher.enrich([context()], "en", OPENAI_OPTIONS)

    assert result["K001"].level2 == LEVEL2
    assert result["K001"].external_sources == ()
    assert len(enricher.llm.synthesis_calls) == 2
    assert len(enricher.llm.review_calls) == 3


@pytest.mark.asyncio
async def test_uncited_research_keeps_approved_transcript_only_plan() -> None:
    enricher = enricher_with(empty_ids={"K001"}, review_results=[True])

    result = await enricher.enrich([context()], "en", OPENAI_OPTIONS)

    assert result["K001"].level2 == PLANNED_LEVEL2
    assert result["K001"].external_sources == ()
    assert enricher.llm.synthesis_calls == []


@pytest.mark.asyncio
async def test_one_failed_occurrence_does_not_affect_siblings() -> None:
    enricher = enricher_with(
        synthesis_errors={
            "K001": AppError(
                502,
                "LLM_ENRICHMENT_SYNTHESIS_INVALID_JSON",
                "malformed",
            )
        }
    )

    result = await enricher.enrich(
        [context("K001"), context("K007")], "en", OPENAI_OPTIONS
    )

    assert result["K001"].level2 == LEVEL2
    assert result["K007"].external_sources == evidence("K007").sources


@pytest.mark.asyncio
async def test_research_concurrency_never_exceeds_configured_limit() -> None:
    enricher = enricher_with(
        delay=0.02,
        settings=Settings(
            explanation_enrichment_enabled=True,
            explanation_enrichment_max_concurrency=2,
            openai_api_key="test-key",
        ),
    )
    contexts = [context(f"K{index:03d}") for index in range(1, 7)]

    await enricher.enrich(contexts, "en", OPENAI_OPTIONS)

    assert enricher.search.max_active_calls == 2


@pytest.mark.asyncio
async def test_cancellation_is_not_converted_to_fallback() -> None:
    enricher = enricher_with(search_error=asyncio.CancelledError())

    with pytest.raises(asyncio.CancelledError):
        await enricher.enrich([context()], "en", OPENAI_OPTIONS)


@pytest.mark.asyncio
async def test_planner_failure_returns_fallback() -> None:
    enricher = enricher_with(
        planner_error=AppError(502, "LLM_ENRICHMENT_PLAN_INVALID_JSON", "bad plan")
    )

    result = await enricher.enrich([context()], "en", OPENAI_OPTIONS)

    assert result["K001"].level2 == LEVEL2
    assert enricher.search.calls == []


@pytest.mark.asyncio
async def test_completion_log_contains_only_counts_and_durations(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret_term = "PRIVATE_TERM_DO_NOT_LOG"
    secret_excerpt = "PRIVATE_EXCERPT_DO_NOT_LOG"
    secret_level = "PRIVATE_PROSE_DO_NOT_LOG"
    secret_url = "https://example.com/K001"
    enricher = enricher_with(
        search_error=AppError(502, "LLM_REQUEST_FAILED", secret_level)
    )

    with caplog.at_level(logging.INFO, logger="reforge.enrichment"):
        await enricher.enrich(
            [
                context(
                    term=secret_term,
                    source_excerpts=(secret_excerpt,),
                    transcript_level2=secret_level,
                )
            ],
            "en",
            OPENAI_OPTIONS,
        )

    records = [
        record for record in caplog.records if record.name == "reforge.enrichment"
    ]
    assert len(records) == 1
    message = records[0].getMessage()
    assert "planned=1" in message
    assert "routed=1" in message
    assert "fallback=1" in message
    assert "retrieval_failure=1" in message
    assert "planner_ms=" in message
    assert "retrieval_ms=" in message
    assert "synthesis_review_ms=" in message
    assert "total_ms=" in message
    for secret in (secret_term, secret_excerpt, secret_level, secret_url):
        assert secret not in message


@pytest.mark.asyncio
async def test_citation_validation_failure_is_counted_without_content(
    caplog: pytest.LogCaptureFixture,
) -> None:
    enricher = enricher_with(
        synthesis_errors={
            "K001": AppError(
                502,
                "LLM_ENRICHMENT_SYNTHESIS_INVALID_JSON",
                "Unknown citation https://private.example/secret",
            )
        }
    )

    with caplog.at_level(logging.INFO, logger="reforge.enrichment"):
        result = await enricher.enrich([context()], "en", OPENAI_OPTIONS)

    assert result["K001"].level2 == LEVEL2
    message = caplog.records[-1].getMessage()
    assert "citation_validation_failure=1" in message
    assert "private.example" not in message
