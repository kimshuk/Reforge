import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import Settings
from app.enrichment import (
    EnrichmentContext,
    EnrichmentPlan,
    OccurrenceEnrichment,
    ResearchEvidence,
)
from app.errors import AppError
from app.llm import LlmClient
from app.openai_search import OpenAIWebSearchClient

LOGGER = logging.getLogger("reforge.enrichment")
EMPTY_EVIDENCE = ResearchEvidence(summary="", sources=())
_RECOVERABLE_ERRORS = (
    AppError,
    httpx.HTTPError,
    TimeoutError,
    TypeError,
    ValueError,
    AttributeError,
)


@dataclass
class _Metrics:
    planned: int = 0
    routed: int = 0
    retrieval_failures: int = 0
    citation_validation_failures: int = 0
    planner_seconds: float = 0
    retrieval_seconds: float = 0
    synthesis_review_seconds: float = 0


class ExplanationEnricher:
    def __init__(
        self,
        llm: LlmClient,
        search: OpenAIWebSearchClient,
        settings: Settings,
    ) -> None:
        self.llm = llm
        self.search = search
        self.settings = settings

    async def enrich(
        self,
        contexts: list[EnrichmentContext],
        target_language: str,
        options: dict[str, Any],
    ) -> dict[str, OccurrenceEnrichment]:
        started = time.monotonic()
        metrics = _Metrics()
        fallbacks = {
            context.keyword_id: _fallback_for(context) for context in contexts
        }
        results = dict(fallbacks)

        if (
            not contexts
            or not self.settings.explanation_enrichment_enabled
            or options.get("provider") != "openai"
        ):
            _log_completion(metrics, results, fallbacks, started)
            return results

        planner_started = time.monotonic()
        try:
            plans = await self.llm.plan_explanation_enrichment(
                contexts, target_language, options
            )
            plans_by_id = _partition_plans(plans, contexts)
        except asyncio.CancelledError:
            raise
        except _RECOVERABLE_ERRORS:
            metrics.planner_seconds = time.monotonic() - planner_started
            _log_completion(metrics, results, fallbacks, started)
            return results
        metrics.planner_seconds = time.monotonic() - planner_started
        metrics.planned = len(plans_by_id)
        metrics.routed = sum(
            plan.needs_external_research for plan in plans_by_id.values()
        )

        eligible_for_research: list[tuple[EnrichmentContext, EnrichmentPlan]] = []
        for context in contexts:
            plan = plans_by_id[context.keyword_id]
            draft = OccurrenceEnrichment(
                keyword_id=context.keyword_id,
                level2=plan.level2,
                level3=plan.level3,
            )
            review_started = time.monotonic()
            try:
                approved = await self.llm.review_explanation_enrichment(
                    context,
                    draft,
                    EMPTY_EVIDENCE,
                    target_language,
                    options,
                )
                if not isinstance(approved, bool):
                    raise TypeError("review result must be a boolean")
            except asyncio.CancelledError:
                raise
            except _RECOVERABLE_ERRORS:
                continue
            finally:
                metrics.synthesis_review_seconds += (
                    time.monotonic() - review_started
                )

            if approved:
                results[context.keyword_id] = draft
            if plan.needs_external_research:
                eligible_for_research.append((context, plan))

        semaphore = asyncio.Semaphore(
            self.settings.explanation_enrichment_max_concurrency
        )

        async def enrich_occurrence(
            context: EnrichmentContext, plan: EnrichmentPlan
        ) -> tuple[str, OccurrenceEnrichment]:
            async with semaphore:
                return context.keyword_id, await self._enrich_occurrence(
                    context,
                    plan,
                    fallbacks[context.keyword_id],
                    results[context.keyword_id],
                    target_language,
                    options,
                    metrics,
                )

        try:
            enriched = await asyncio.gather(
                *(enrich_occurrence(context, plan) for context, plan in eligible_for_research)
            )
        except asyncio.CancelledError:
            raise
        for keyword_id, enrichment in enriched:
            results[keyword_id] = enrichment

        _log_completion(metrics, results, fallbacks, started)
        return results

    async def _enrich_occurrence(
        self,
        context: EnrichmentContext,
        plan: EnrichmentPlan,
        fallback: OccurrenceEnrichment,
        transcript_result: OccurrenceEnrichment,
        target_language: str,
        options: dict[str, Any],
        metrics: _Metrics,
    ) -> OccurrenceEnrichment:
        retrieval_started = time.monotonic()
        try:
            evidence = await self.search.research_occurrence(context, plan, options)
            if not isinstance(evidence, ResearchEvidence):
                raise TypeError("research result must be ResearchEvidence")
        except asyncio.CancelledError:
            raise
        except _RECOVERABLE_ERRORS:
            metrics.retrieval_failures += 1
            return fallback
        finally:
            metrics.retrieval_seconds += time.monotonic() - retrieval_started

        if not evidence.sources:
            return transcript_result

        synthesis_started = time.monotonic()
        try:
            for attempt in range(2):
                candidate = await self.llm.synthesize_explanation_enrichment(
                    context,
                    plan,
                    evidence,
                    target_language,
                    options,
                )
                if (
                    not isinstance(candidate, OccurrenceEnrichment)
                    or candidate.keyword_id != context.keyword_id
                ):
                    raise TypeError("synthesis result has an invalid occurrence ID")
                approved = await self.llm.review_explanation_enrichment(
                    context,
                    candidate,
                    evidence,
                    target_language,
                    options,
                )
                if not isinstance(approved, bool):
                    raise TypeError("review result must be a boolean")
                if approved:
                    return candidate
                if attempt == 1:
                    return fallback
        except asyncio.CancelledError:
            raise
        except AppError as error:
            if error.code == "LLM_ENRICHMENT_SYNTHESIS_INVALID_JSON":
                metrics.citation_validation_failures += 1
            return fallback
        except (httpx.HTTPError, TimeoutError, TypeError, ValueError, AttributeError):
            return fallback
        finally:
            metrics.synthesis_review_seconds += time.monotonic() - synthesis_started

        return fallback


def _fallback_for(context: EnrichmentContext) -> OccurrenceEnrichment:
    return OccurrenceEnrichment(
        keyword_id=context.keyword_id,
        level2=context.transcript_level2,
        level3=context.transcript_level3,
    )


def _partition_plans(
    plans: list[EnrichmentPlan], contexts: list[EnrichmentContext]
) -> dict[str, EnrichmentPlan]:
    if not isinstance(plans, list) or any(
        not isinstance(plan, EnrichmentPlan) for plan in plans
    ):
        raise TypeError("planner result must contain enrichment plans")
    expected_ids = [context.keyword_id for context in contexts]
    plan_ids = [plan.keyword_id for plan in plans]
    if (
        len(expected_ids) != len(set(expected_ids))
        or len(plan_ids) != len(set(plan_ids))
        or len(plan_ids) != len(expected_ids)
        or set(plan_ids) != set(expected_ids)
    ):
        raise ValueError("planner occurrence IDs must partition contexts exactly once")
    return {plan.keyword_id: plan for plan in plans}


def _log_completion(
    metrics: _Metrics,
    results: dict[str, OccurrenceEnrichment],
    fallbacks: dict[str, OccurrenceEnrichment],
    started: float,
) -> None:
    fallback_count = sum(
        result == fallbacks.get(keyword_id) for keyword_id, result in results.items()
    )
    LOGGER.info(
        "explanation_enrichment_complete planned=%d routed=%d enriched=%d "
        "fallback=%d retrieval_failure=%d citation_validation_failure=%d "
        "planner_ms=%.2f retrieval_ms=%.2f synthesis_review_ms=%.2f total_ms=%.2f",
        metrics.planned,
        metrics.routed,
        len(results) - fallback_count,
        fallback_count,
        metrics.retrieval_failures,
        metrics.citation_validation_failures,
        metrics.planner_seconds * 1000,
        metrics.retrieval_seconds * 1000,
        metrics.synthesis_review_seconds * 1000,
        (time.monotonic() - started) * 1000,
    )
