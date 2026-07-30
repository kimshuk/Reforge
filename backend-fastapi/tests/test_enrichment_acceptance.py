from collections import defaultdict

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

OPTIONS = {"provider": "openai", "model": "gpt-4o-mini"}


def occurrence(keyword_id: str, excerpt: str = "Codex handles delegated work.") -> EnrichmentContext:
    return EnrichmentContext(
        keyword_id, "Codex", "entity", "Autonomous coding tool introduced here",
        "Codex is a tool that performs coding tasks.", "Coding agents",
        "The speaker discusses autonomous coding.", (excerpt,),
        "The speaker introduces Codex as a coding tool. It handles delegated work.",
        "The speaker introduces Codex as a coding tool. It accepts delegated tasks. This changes the coding workflow.",
        ("Coding agents: autonomous tools",),
    )


def plan(context: EnrichmentContext, research: bool) -> EnrichmentPlan:
    return EnrichmentPlan(
        context.keyword_id,
        context.transcript_level2,
        context.transcript_level3,
        research,
        "Find current supporting documentation." if research else "",
        "current" if research else "none",
    )


def evidence(keyword_id: str) -> ResearchEvidence:
    return ResearchEvidence(
        "Current supporting evidence.",
        (ResearchSource("C1", f"Source {keyword_id}", f"https://example.com/{keyword_id}", "Support"),),
    )


class AcceptanceLlm:
    def __init__(self, research_ids=(), rejected_ids=()) -> None:
        self.research_ids = set(research_ids)
        self.rejected_ids = set(rejected_ids)
        self.review_counts = defaultdict(int)

    async def plan_explanation_enrichment(self, contexts, _language, _options):
        return [plan(item, item.keyword_id in self.research_ids) for item in contexts]

    async def synthesize_explanation_enrichment(self, context, _plan, found, _language, _options):
        return OccurrenceEnrichment(
            context.keyword_id,
            context.transcript_level2,
            context.transcript_level3,
            level3_citation_ids=("C1",),
            external_sources=found.sources,
        )

    async def review_explanation_enrichment(self, context, _candidate, found, _language, _options):
        if found.sources:
            self.review_counts[context.keyword_id] += 1
            return context.keyword_id not in self.rejected_ids
        return True


class AcceptanceSearch:
    def __init__(self, failures=()) -> None:
        self.failures = set(failures)
        self.calls: list[str] = []

    async def research_occurrence(self, context, _plan, _options):
        self.calls.append(context.keyword_id)
        if context.keyword_id in self.failures:
            raise AppError(502, "LLM_REQUEST_FAILED", "failed")
        return evidence(context.keyword_id)


def enricher(research_ids=(), rejected_ids=(), failures=()):
    search = AcceptanceSearch(failures)
    service = ExplanationEnricher(
        AcceptanceLlm(research_ids, rejected_ids),
        search,
        Settings(explanation_enrichment_enabled=True),
    )
    return service, search


@pytest.mark.asyncio
async def test_complete_transcript_explanation_performs_no_search() -> None:
    service, search = enricher()
    result = await service.enrich([occurrence("K001")], "en", OPTIONS)
    assert search.calls == []
    assert result["K001"].external_sources == ()


@pytest.mark.asyncio
async def test_current_occurrence_gets_cited_level3_detail() -> None:
    service, _ = enricher({"K001"})
    result = await service.enrich([occurrence("K001")], "en", OPTIONS)
    assert result["K001"].level3_citation_ids == ("C1",)


@pytest.mark.asyncio
async def test_search_failure_isolated_from_enriched_sibling() -> None:
    service, _ = enricher({"K001", "K002"}, failures={"K001"})
    result = await service.enrich([occurrence("K001"), occurrence("K002")], "en", OPTIONS)
    assert result["K001"].external_sources == ()
    assert result["K002"].external_sources[0].url.endswith("/K002")


@pytest.mark.asyncio
async def test_same_term_occurrences_keep_independent_citations() -> None:
    service, _ = enricher({"K001", "K007"})
    result = await service.enrich(
        [occurrence("K001", "Introduced as a tool."), occurrence("K007", "Presented as a risk.")],
        "en", OPTIONS,
    )
    assert set(result) == {"K001", "K007"}
    assert result["K001"].external_sources != result["K007"].external_sources


@pytest.mark.asyncio
async def test_contradictory_evidence_rejection_returns_transcript_only() -> None:
    service, _ = enricher({"K001"}, rejected_ids={"K001"})
    context = occurrence("K001")
    result = await service.enrich([context], "en", OPTIONS)
    assert result["K001"].level3 == context.transcript_level3
    assert result["K001"].external_sources == ()
