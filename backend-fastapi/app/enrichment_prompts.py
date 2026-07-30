import json

from app.enrichment import (
    EnrichmentContext,
    EnrichmentPlan,
    OccurrenceEnrichment,
    ResearchEvidence,
)

ENRICHMENT_PLAN_SCHEMA: dict[str, object] = {
    "name": "explanation_enrichment_plan",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["plans"],
        "properties": {
            "plans": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "keywordId",
                        "level2",
                        "level3",
                        "needsExternalResearch",
                        "researchQuestion",
                        "preferredSourceClass",
                    ],
                    "properties": {
                        "keywordId": {"type": "string", "minLength": 1},
                        "level2": {"type": "string", "minLength": 1},
                        "level3": {"type": "string", "minLength": 1},
                        "needsExternalResearch": {"type": "boolean"},
                        "researchQuestion": {"type": "string"},
                        "preferredSourceClass": {
                            "type": "string",
                            "enum": ["official", "research", "reference", "current", "none"],
                        },
                    },
                },
            }
        },
    },
}

ENRICHMENT_SYNTHESIS_SCHEMA: dict[str, object] = {
    "name": "explanation_enrichment_synthesis",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "keywordId",
            "level2",
            "level3",
            "level2CitationIds",
            "level3CitationIds",
        ],
        "properties": {
            "keywordId": {"type": "string", "minLength": 1},
            "level2": {"type": "string", "minLength": 1},
            "level3": {"type": "string", "minLength": 1},
            "level2CitationIds": {"type": "array", "items": {"type": "string"}},
            "level3CitationIds": {"type": "array", "items": {"type": "string"}},
        },
    },
}

ENRICHMENT_REVIEW_SCHEMA: dict[str, object] = {
    "name": "explanation_enrichment_review",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["approved", "reasonCode"],
        "properties": {
            "approved": {"type": "boolean"},
            "reasonCode": {"type": "string", "minLength": 1},
        },
    },
}


def enrichment_plan_prompt(
    contexts: list[EnrichmentContext], target_language: str
) -> tuple[str, str]:
    return (
        _shared_rules(target_language)
        + """\nYou plan additive level2 and level3 explanation enrichment for each occurrence.

Return every keywordId exactly once. Keep same-term occurrences separate by keywordId.
Use transcript material first. Request external research only when it materially improves
the explanation. For no research, use an empty researchQuestion and source class none.

Good example:
{"plans":[{"keywordId":"K001","level2":"Two transcript-grounded sentences. Another sentence adds occurrence context.","level3":"One detailed sentence. A second adds reasoning. A third explains the implication.","needsExternalResearch":false,"researchQuestion":"","preferredSourceClass":"none"}]}

Bad example:
{"plans":[{"keywordId":"Pricing Pressure","level2":"Unchanged.","level3":"Unchanged.","needsExternalResearch":true,"researchQuestion":"","preferredSourceClass":"none"}]}

Return only JSON matching the schema.""",
        "Occurrences:\n" + _json([_context_payload(context) for context in contexts]),
    )


def enrichment_synthesis_prompt(
    context: EnrichmentContext,
    plan: EnrichmentPlan,
    evidence: ResearchEvidence,
    target_language: str,
) -> tuple[str, str]:
    return (
        _shared_rules(target_language)
        + """\nYou synthesize one additive explanation for the supplied occurrence and plan.
Use only the supplied transcript and evidence. Every external claim requires supplied
citation IDs in level2CitationIds or level3CitationIds. Do not cite unused sources.

Good example:
{"keywordId":"K001","level2":"The speaker makes the first claim. The supplied evidence clarifies the mechanism.","level3":"The speaker makes the claim. The evidence supports the mechanism. This adds a bounded implication.","level2CitationIds":["C1"],"level3CitationIds":["C1"]}

Bad example:
{"keywordId":"Pricing Pressure","simpleExplanation":"A changed level1 definition.","level2":"One sentence.","level3":"An uncited external fact."}

Return only JSON matching the schema.""",
        _json(
            {
                "occurrence": _context_payload(context),
                "plan": _plan_payload(plan),
                "evidence": _evidence_payload(evidence),
            }
        ),
    )


def enrichment_review_prompt(
    context: EnrichmentContext,
    enrichment: OccurrenceEnrichment,
    evidence: ResearchEvidence,
    target_language: str,
) -> tuple[str, str]:
    return (
        _shared_rules(target_language)
        + """\nYou review whether one additive enrichment is supported by its occurrence and evidence.
Approve only supported, occurrence-local additions with valid supplied citations.

Good example:
{"approved":true,"reasonCode":"supported_additive_enrichment"}

Bad example:
{"approved":true,"reasonCode":"corrected_the_speaker_with_conflicting_evidence"}

Return only JSON matching the schema.""",
        _json(
            {
                "occurrence": _context_payload(context),
                "enrichment": _enrichment_payload(enrichment),
                "evidence": _evidence_payload(evidence),
            }
        ),
    )


def _shared_rules(target_language: str) -> str:
    return f"""Write explanatory text in {target_language}.

Rules:
- The topic outline is for disambiguation only; it is not evidence.
- level1 is immutable and must not be changed or returned.
- External claims require supplied citation IDs.
- Contradictory evidence requires fallback rather than correction of the speaker.
- Keep level2 at 2-3 sentences and level3 at 3-5 sentences.
- Keep all explanations distinct and progressively more detailed."""


def _context_payload(context: EnrichmentContext) -> dict[str, object]:
    return {
        "keywordId": context.keyword_id,
        "term": context.term,
        "kind": context.kind,
        "brief": context.brief,
        "level1": context.simple_explanation,
        "chunkTitle": context.chunk_title,
        "chunkSummary": context.chunk_summary,
        "sourceExcerpts": list(context.source_excerpts),
        "transcriptLevel2": context.transcript_level2,
        "transcriptLevel3": context.transcript_level3,
        "videoTopicOutline": list(context.video_topic_outline),
    }


def _plan_payload(plan: EnrichmentPlan) -> dict[str, object]:
    return {
        "keywordId": plan.keyword_id,
        "level2": plan.level2,
        "level3": plan.level3,
        "needsExternalResearch": plan.needs_external_research,
        "researchQuestion": plan.research_question,
        "preferredSourceClass": plan.preferred_source_class,
    }


def _evidence_payload(evidence: ResearchEvidence) -> dict[str, object]:
    return {
        "summary": evidence.summary,
        "sources": [
            {
                "citationId": source.citation_id,
                "title": source.title,
                "url": source.url,
                "supportingText": source.supporting_text,
            }
            for source in evidence.sources
        ],
    }


def _enrichment_payload(enrichment: OccurrenceEnrichment) -> dict[str, object]:
    return {
        "keywordId": enrichment.keyword_id,
        "level2": enrichment.level2,
        "level3": enrichment.level3,
        "level2CitationIds": list(enrichment.level2_citation_ids),
        "level3CitationIds": list(enrichment.level3_citation_ids),
    }


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)
