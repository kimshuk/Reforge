from typing import Any

TOPIC_CHUNKING_SCHEMA: dict[str, Any] = {
    "name": "topic_chunking",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["topicChunks"],
        "properties": {
            "topicChunks": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "startSegmentId",
                        "endSegmentId",
                        "title",
                        "summary",
                        "signalLevel",
                    ],
                    "properties": {
                        "startSegmentId": {"type": "string"},
                        "endSegmentId": {"type": "string"},
                        "title": {"type": "string", "minLength": 3, "maxLength": 80},
                        "summary": {"type": "string", "minLength": 3, "maxLength": 300},
                        "signalLevel": {
                            "type": "string",
                            "enum": ["high", "medium", "low", "off_topic"],
                        },
                    },
                },
            }
        },
    },
}

CANDIDATE_CLIPPING_SCHEMA: dict[str, Any] = {
    "name": "candidate_clipping",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["candidateClippings"],
        "properties": {
            "candidateClippings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "kind",
                        "title",
                        "text",
                        "brief",
                        "simpleExplanation",
                        "contextualExplanation",
                        "detailedExplanation",
                        "signalLevel",
                        "sourceRefs",
                    ],
                    "properties": {
                        "kind": {
                            "type": "string",
                            "enum": [
                                "topic", "claim", "mechanism", "risk", "trend",
                                "entity", "example", "question", "contradiction",
                            ],
                        },
                        "title": {"type": "string", "minLength": 2, "maxLength": 60},
                        "text": {"type": "string", "minLength": 3, "maxLength": 500},
                        "brief": {"type": "string", "minLength": 3, "maxLength": 90},
                        "simpleExplanation": {"type": "string", "minLength": 3, "maxLength": 180},
                        "contextualExplanation": {"type": "string", "minLength": 3, "maxLength": 420},
                        "detailedExplanation": {"type": "string", "minLength": 3, "maxLength": 700},
                        "signalLevel": {"type": "string", "enum": ["high", "medium", "low"]},
                        "sourceRefs": {
                            "type": "array",
                            "minItems": 1,
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["startSegmentId", "endSegmentId", "timestamp", "text"],
                                "properties": {
                                    "startSegmentId": {"type": "string"},
                                    "endSegmentId": {"type": "string"},
                                    "timestamp": {"type": "string"},
                                    "text": {"type": "string", "minLength": 3, "maxLength": 300},
                                },
                            },
                        },
                    },
                },
            }
        },
    },
}

CATEGORY_GROUPING_SCHEMA: dict[str, Any] = {
    "name": "keyword_category_grouping",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["categories"],
        "properties": {
            "categories": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["title", "keywordIds"],
                    "properties": {
                        "title": {"type": "string", "minLength": 2, "maxLength": 80},
                        "keywordIds": {
                            "type": "array",
                            "minItems": 1,
                            "items": {"type": "string"},
                        },
                    },
                },
            }
        },
    },
}


def topic_chunking_prompt(segments: str, target_language: str) -> tuple[str, str]:
    return (
        f"""You split transcript segments into coherent topic chunks.

Return boundaries only. Do not write chunk text.

Rules:
- Use only segment IDs that appear in the transcript.
- Chunks must be ordered and non-overlapping.
- Each major topic shift should become a chunk.
- Sponsor reads, intros, repeated content, and tangents should be low or off_topic when large enough to affect coverage.
- Write title and summary in {target_language}.

Return only JSON matching the schema.""",
        f"Transcript segments:\n{segments}",
    )


def candidate_clipping_prompt(
    chunk_title: str, chunk_summary: str, segments: str, target_language: str
) -> tuple[str, str]:
    return (
        f"""You extract reusable candidate clippings from a topic chunk.

Keep candidates neutral. Extract only useful ideas grounded in the chunk. Every candidate must include at least one sourceRef using segment IDs from this chunk. Use no external facts. Write all explanatory fields in {target_language}.

Explanation ladder contract:
- title is the compatibility term: a short reusable concept label, preferably a noun phrase, never a sentence, at most 60 characters.
- brief is a 5-10 word glanceable explanation and must be shorter than simpleExplanation.
- simpleExplanation is exactly one simple beginner-friendly definition. It explains the term without relying on this video.
- contextualExplanation is 2-3 sentences explaining how the term appears in this specific chunk, grounded in its transcript.
- detailedExplanation is 3-5 sentences adding the speaker's claim, reasoning, mechanism, implication, risk, or example when available. It must stay source-grounded.
- The three explanation levels must be non-empty, distinct, progressively longer, and add new information rather than paraphrasing one another.

Good example:
{{
  "title": "Pricing Pressure",
  "brief": "Competitors are pushing product prices downward",
  "simpleExplanation": "Pricing pressure means outside forces make prices harder to maintain.",
  "contextualExplanation": "In this chunk, the speaker says competitors are pushing prices down. They connect that pressure to the team needing a clearer response.",
  "detailedExplanation": "The speaker claims competitors are pushing prices down and making the current approach harder to defend. Their reasoning is that buyers compare the options discussed in the chunk more directly. This mechanism forces the team to clarify its response. The implication is that pricing cannot remain a static decision in this discussion."
}}

Bad example:
{{
  "title": "Pricing is hard.",
  "brief": "Pricing is hard",
  "simpleExplanation": "Pricing is hard.",
  "contextualExplanation": "Pricing is hard.",
  "detailedExplanation": "Pricing is hard."
}}

Return only JSON matching the schema.""",
        f"Chunk title: {chunk_title}\nChunk summary: {chunk_summary}\nChunk segments:\n{segments}",
    )


def category_grouping_prompt(occurrences: str, target_language: str) -> tuple[str, str]:
    return (
        f"""You assign contextual keyword occurrence IDs to semantic categories.

Rules:
- Return every provided keywordId exactly once.
- Use only the provided keywordIds. Never invent, rewrite, omit, duplicate, or merge IDs.
- Equal display terms may represent different contextual occurrences and must remain separate IDs.
- Categories are semantic groups without timestamps and must contain at least one keywordId.
- A category may contain repeated display terms from different transcript sections.
- If an occurrence does not fit another group, create a meaningful singleton category rather than omitting it or using a generic fallback.
- Write category titles in {target_language}.

Good example:
{{
  "categories": [
    {{"title": "OpenAI", "keywordIds": ["K001", "K007"]}}
  ]
}}

Bad example:
{{
  "categories": [
    {{"title": "OpenAI", "keywordIds": ["Codex"]}}
  ]
}}

The bad example rewrites occurrence IDs as display terms and may merge separate occurrences.
Return only JSON matching the schema.""",
        f"Keyword occurrences:\n{occurrences}",
    )
