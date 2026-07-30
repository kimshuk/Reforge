from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlparse

from app.errors import AppError
from app.explanation_validation import validate_explanation_ladder

PLAN_ERROR_CODE = "LLM_ENRICHMENT_PLAN_INVALID_JSON"
SYNTHESIS_ERROR_CODE = "LLM_ENRICHMENT_SYNTHESIS_INVALID_JSON"
SOURCE_CLASSES = {"official", "research", "reference", "current", "none"}


@dataclass(frozen=True)
class EnrichmentContext:
    keyword_id: str
    term: str
    kind: str
    brief: str
    simple_explanation: str
    chunk_title: str
    chunk_summary: str
    source_excerpts: tuple[str, ...]
    transcript_level2: str
    transcript_level3: str
    video_topic_outline: tuple[str, ...]


@dataclass(frozen=True)
class EnrichmentPlan:
    keyword_id: str
    level2: str
    level3: str
    needs_external_research: bool
    research_question: str
    preferred_source_class: Literal["official", "research", "reference", "current", "none"]


@dataclass(frozen=True)
class ResearchSource:
    citation_id: str
    title: str
    url: str
    supporting_text: str


@dataclass(frozen=True)
class ResearchEvidence:
    summary: str
    sources: tuple[ResearchSource, ...]


@dataclass(frozen=True)
class OccurrenceEnrichment:
    keyword_id: str
    level2: str
    level3: str
    level2_citation_ids: tuple[str, ...] = ()
    level3_citation_ids: tuple[str, ...] = ()
    external_sources: tuple[ResearchSource, ...] = ()


def validate_plan_payload(value: Any, contexts: list[EnrichmentContext]) -> list[EnrichmentPlan]:
    errors: list[str] = []
    context_by_id = _contexts_by_id(contexts, errors)
    if not isinstance(value, dict) or set(value) != {"plans"}:
        raise AppError(502, PLAN_ERROR_CODE, "Plan payload must contain only plans")
    plans = value["plans"]
    if not isinstance(plans, list):
        raise AppError(502, PLAN_ERROR_CODE, "plans must be an array")

    validated: list[EnrichmentPlan] = []
    assigned_ids: list[str] = []
    for index, raw_plan in enumerate(plans):
        plan, plan_errors = _validate_plan(raw_plan, index, context_by_id)
        errors.extend(plan_errors)
        if plan is not None:
            validated.append(plan)
            assigned_ids.append(plan.keyword_id)

    expected_ids = [context.keyword_id for context in contexts]
    if len(assigned_ids) != len(set(assigned_ids)):
        errors.append("Each occurrence must be assigned at most once")
    if set(assigned_ids) != set(expected_ids) or len(assigned_ids) != len(expected_ids):
        errors.append("Every occurrence must be assigned exactly once")
    if errors:
        raise AppError(502, PLAN_ERROR_CODE, "; ".join(errors))
    return validated


def validate_synthesis_payload(
    value: Any, context: EnrichmentContext, evidence: ResearchEvidence
) -> OccurrenceEnrichment:
    errors = _validate_evidence(evidence)
    if not isinstance(value, dict):
        raise AppError(502, SYNTHESIS_ERROR_CODE, "Synthesis payload must be an object")

    expected_fields = {
        "keywordId",
        "level2",
        "level3",
        "level2CitationIds",
        "level3CitationIds",
    }
    extra_fields = set(value) - expected_fields
    immutable_fields = extra_fields & {"level1", "simpleExplanation"}
    if immutable_fields:
        errors.append(f"{sorted(immutable_fields)[0]} is immutable")
    if extra_fields - immutable_fields:
        errors.append("Synthesis payload contains unsupported fields")
    missing_fields = expected_fields - set(value)
    if missing_fields:
        errors.append("Synthesis payload is missing required fields")

    keyword_id = value.get("keywordId")
    if not isinstance(keyword_id, str) or not keyword_id.strip():
        errors.append("keywordId must be a non-empty string")
    elif keyword_id.strip() != context.keyword_id:
        errors.append("keywordId is immutable")

    level2 = value.get("level2")
    level3 = value.get("level3")
    if not isinstance(level2, str) or not level2.strip():
        errors.append("level2 must be a non-empty string")
    if not isinstance(level3, str) or not level3.strip():
        errors.append("level3 must be a non-empty string")
    if isinstance(level2, str) and isinstance(level3, str):
        try:
            validate_explanation_ladder(
                context.term,
                context.brief,
                context.simple_explanation,
                level2.strip(),
                level3.strip(),
            )
        except AppError as error:
            errors.append(error.message)

    sources = evidence.sources if isinstance(evidence, ResearchEvidence) else ()
    known_citation_ids = {
        source.citation_id.strip()
        for source in sources
        if isinstance(source, ResearchSource) and isinstance(source.citation_id, str)
    }
    level2_citations = _validate_citation_ids(
        value.get("level2CitationIds"), "level2CitationIds", known_citation_ids, errors
    )
    level3_citations = _validate_citation_ids(
        value.get("level3CitationIds"), "level3CitationIds", known_citation_ids, errors
    )
    if errors:
        raise AppError(502, SYNTHESIS_ERROR_CODE, "; ".join(errors))

    used_citation_ids = set(level2_citations) | set(level3_citations)
    external_sources = tuple(
        source for source in sources if source.citation_id in used_citation_ids
    )
    return OccurrenceEnrichment(
        keyword_id=context.keyword_id,
        level2=level2.strip(),
        level3=level3.strip(),
        level2_citation_ids=level2_citations,
        level3_citation_ids=level3_citations,
        external_sources=external_sources,
    )


def _contexts_by_id(
    contexts: list[EnrichmentContext], errors: list[str]
) -> dict[str, EnrichmentContext]:
    context_by_id: dict[str, EnrichmentContext] = {}
    for context in contexts:
        if context.keyword_id in context_by_id:
            errors.append("Context occurrence IDs must be unique")
        context_by_id[context.keyword_id] = context
    return context_by_id


def _validate_plan(
    value: Any, index: int, contexts: dict[str, EnrichmentContext]
) -> tuple[EnrichmentPlan | None, list[str]]:
    errors: list[str] = []
    fields = {
        "keywordId",
        "level2",
        "level3",
        "needsExternalResearch",
        "researchQuestion",
        "preferredSourceClass",
    }
    if not isinstance(value, dict) or set(value) != fields:
        return None, [f"Plan {index} must contain the required fields only"]

    keyword_id = value["keywordId"]
    level2 = value["level2"]
    level3 = value["level3"]
    needs_research = value["needsExternalResearch"]
    research_question = value["researchQuestion"]
    source_class = value["preferredSourceClass"]
    if not isinstance(keyword_id, str) or not keyword_id.strip():
        errors.append(f"Plan {index} keywordId must be a non-empty string")
    elif keyword_id.strip() not in contexts:
        errors.append(f"Plan {index} contains an unknown occurrence ID")
    if not isinstance(level2, str) or not level2.strip():
        errors.append(f"Plan {index} level2 must be a non-empty string")
    if not isinstance(level3, str) or not level3.strip():
        errors.append(f"Plan {index} level3 must be a non-empty string")
    if not isinstance(needs_research, bool):
        errors.append(f"Plan {index} needsExternalResearch must be a boolean")
    if not isinstance(research_question, str):
        errors.append(f"Plan {index} researchQuestion must be a string")
    if not isinstance(source_class, str) or source_class not in SOURCE_CLASSES:
        errors.append(f"Plan {index} preferredSourceClass is invalid")

    context = contexts.get(keyword_id.strip()) if isinstance(keyword_id, str) else None
    if context and isinstance(level2, str) and isinstance(level3, str):
        try:
            validate_explanation_ladder(
                context.term,
                context.brief,
                context.simple_explanation,
                level2.strip(),
                level3.strip(),
            )
        except AppError as error:
            errors.append(f"Plan {index}: {error.message}")

    clean_question = research_question.strip() if isinstance(research_question, str) else ""
    if needs_research is True:
        if not clean_question:
            errors.append(f"Plan {index} needs a research question")
        if source_class == "none":
            errors.append(f"Plan {index} needs a source class when research is requested")
    elif needs_research is False:
        if clean_question:
            errors.append(f"Plan {index} must not include a research question without research")
        if source_class != "none":
            errors.append(f"Plan {index} must use source class none without research")

    if errors:
        return None, errors
    return (
        EnrichmentPlan(
            keyword_id=keyword_id.strip(),
            level2=level2.strip(),
            level3=level3.strip(),
            needs_external_research=needs_research,
            research_question=clean_question,
            preferred_source_class=source_class,
        ),
        [],
    )


def _validate_evidence(evidence: ResearchEvidence) -> list[str]:
    errors: list[str] = []
    if not isinstance(evidence, ResearchEvidence):
        return ["Research evidence is invalid"]
    if not isinstance(evidence.summary, str):
        errors.append("Research evidence summary must be a string")
    if not isinstance(evidence.sources, tuple):
        errors.append("Research evidence sources must be a tuple")
        return errors
    if len(evidence.sources) > 3:
        errors.append("Research evidence may contain at most three sources")
    citation_ids: set[str] = set()
    for index, source in enumerate(evidence.sources):
        if not isinstance(source, ResearchSource):
            errors.append(f"Research source {index} is invalid")
            continue
        if not isinstance(source.citation_id, str) or not source.citation_id.strip():
            errors.append(f"Research source {index} citation ID must be non-empty")
        elif source.citation_id.strip() in citation_ids:
            errors.append("Research source citation IDs must be unique")
        else:
            citation_ids.add(source.citation_id.strip())
        if not isinstance(source.title, str) or not source.title.strip():
            errors.append(f"Research source {index} title must be non-empty")
        if not isinstance(source.supporting_text, str) or not source.supporting_text.strip():
            errors.append(f"Research source {index} supporting text must be non-empty")
        if not _is_absolute_http_url(source.url):
            errors.append(f"Research source {index} URL must be an absolute HTTP(S) URL")
    return errors


def _validate_citation_ids(
    value: Any, field: str, known_ids: set[str], errors: list[str]
) -> tuple[str, ...]:
    if not isinstance(value, list):
        errors.append(f"{field} citation IDs must be an array")
        return ()
    citation_ids: list[str] = []
    for index, citation_id in enumerate(value):
        if not isinstance(citation_id, str) or not citation_id.strip():
            errors.append(f"{field} citation ID {index} must be a non-empty string")
            continue
        clean_id = citation_id.strip()
        if clean_id in citation_ids:
            errors.append(f"{field} citation IDs must be unique")
        elif clean_id not in known_ids:
            errors.append(f"{field} contains an unknown citation ID: {clean_id}")
        citation_ids.append(clean_id)
    return tuple(citation_ids)


def _is_absolute_http_url(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
