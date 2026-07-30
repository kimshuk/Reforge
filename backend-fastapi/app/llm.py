import json
import re
from typing import Any

import httpx

from app.config import Settings
from app.enrichment import (
    EnrichmentContext,
    EnrichmentPlan,
    OccurrenceEnrichment,
    ResearchEvidence,
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
from app.explanation_validation import (
    explanation_ladder_errors,
    sentence_count,
    validate_explanation_ladder,
)
from app.prompts import (
    CANDIDATE_CLIPPING_SCHEMA,
    CATEGORY_GROUPING_SCHEMA,
    TOPIC_CHUNKING_SCHEMA,
    candidate_clipping_prompt,
    category_grouping_prompt,
    topic_chunking_prompt,
)

__all__ = [
    "explanation_ladder_errors",
    "sentence_count",
    "validate_explanation_ladder",
]

PROVIDERS = {"openai", "gemini", "claude"}
MAX_CANDIDATE_GENERATION_ATTEMPTS = 3
DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "gemini": "gemini-1.5-flash",
    "claude": "claude-3-5-haiku-latest",
}


def resolve_llm_options(source: Any, settings: Settings) -> dict[str, Any]:
    raw_provider = source.provider if source.provider is not None else settings.llm_provider
    if not isinstance(raw_provider, str):
        raise AppError(400, "INVALID_LLM_PROVIDER", "provider must be openai, gemini, or claude")
    provider = raw_provider.strip().lower()
    if provider not in PROVIDERS:
        raise AppError(400, "INVALID_LLM_PROVIDER", "provider must be openai, gemini, or claude")
    model = source.model if source.model is not None else settings.llm_model or DEFAULT_MODELS[provider]
    if not isinstance(model, str) or not model.strip():
        raise AppError(400, "INVALID_LLM_MODEL", "model must be a non-empty string")
    raw_temperature = source.temperature if source.temperature is not None else settings.llm_temperature
    try:
        temperature = float(raw_temperature)
    except (TypeError, ValueError) as error:
        raise AppError(400, "INVALID_LLM_TEMPERATURE", "temperature must be a number between 0 and 2") from error
    if not 0 <= temperature <= 2:
        raise AppError(400, "INVALID_LLM_TEMPERATURE", "temperature must be a number between 0 and 2")
    raw_max_tokens = (
        source.max_output_tokens
        if source.max_output_tokens is not None
        else settings.llm_max_output_tokens
    )
    if raw_max_tokens is None or raw_max_tokens == "":
        max_tokens = None
    else:
        try:
            max_tokens = int(raw_max_tokens)
        except (TypeError, ValueError) as error:
            raise AppError(400, "INVALID_LLM_MAX_OUTPUT_TOKENS", "maxOutputTokens must be an integer between 256 and 20000") from error
        if isinstance(raw_max_tokens, float) and not raw_max_tokens.is_integer():
            max_tokens = -1
    if max_tokens is not None and not 256 <= max_tokens <= 20000:
        raise AppError(
            400,
            "INVALID_LLM_MAX_OUTPUT_TOKENS",
            "maxOutputTokens must be an integer between 256 and 20000",
        )
    return {
        "provider": provider,
        "model": model.strip(),
        "temperature": temperature,
        **({"maxOutputTokens": max_tokens} if max_tokens is not None else {}),
    }


class LlmClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self.client = client

    async def generate_topic_chunks(
        self, segments: str, target_language: str, options: dict[str, Any]
    ) -> list[dict[str, Any]]:
        system, user = topic_chunking_prompt(segments, target_language)
        raw = await self._generate(system, user, options, TOPIC_CHUNKING_SCHEMA)
        payload = parse_json_object(raw, "LLM_TOPIC_CHUNKS_INVALID_JSON")
        chunks = payload.get("topicChunks")
        if not isinstance(chunks, list) or not chunks:
            raise AppError(502, "LLM_TOPIC_CHUNKS_EMPTY", "No topic chunks returned")
        valid: list[dict[str, Any]] = []
        for index, chunk in enumerate(chunks):
            if not isinstance(chunk, dict) or not all(
                isinstance(chunk.get(key), str)
                for key in ("startSegmentId", "endSegmentId", "title", "summary", "signalLevel")
            ) or chunk["signalLevel"] not in {"high", "medium", "low", "off_topic"}:
                raise AppError(502, "LLM_TOPIC_CHUNKS_INVALID_JSON", f"Invalid topic chunk at index {index}")
            valid.append({key: value.strip() if isinstance(value, str) else value for key, value in chunk.items()})
        return valid

    async def generate_candidate_clippings(
        self,
        chunk_title: str,
        chunk_summary: str,
        segments: str,
        target_language: str,
        options: dict[str, Any],
    ) -> list[dict[str, Any]]:
        system, user = candidate_clipping_prompt(
            chunk_title, chunk_summary, segments, target_language
        )
        labels = [
            match.group(1)
            for line in segments.splitlines()
            if (match := re.match(r"^\s*([^|\s]+)\s*\|", line))
        ]
        request_user = user
        for attempt in range(MAX_CANDIDATE_GENERATION_ATTEMPTS):
            raw = await self._generate(
                system, request_user, options, CANDIDATE_CLIPPING_SCHEMA
            )
            try:
                payload = parse_json_object(raw, "LLM_CLIPPINGS_INVALID_JSON")
                candidates = payload.get("candidateClippings")
                if not isinstance(candidates, list):
                    raise AppError(
                        502,
                        "LLM_CLIPPINGS_INVALID_JSON",
                        "Invalid candidate clipping list",
                    )
                return validate_candidates(candidates, labels)
            except AppError as error:
                retryable = error.code in {
                    "LLM_CLIPPINGS_INVALID_JSON",
                    "LLM_CLIPPINGS_INVALID_SOURCE_REF",
                }
                if attempt == MAX_CANDIDATE_GENERATION_ATTEMPTS - 1 or not retryable:
                    raise
                request_user = (
                    f"{user}\n\n"
                    "Correction required: the previous response failed semantic "
                    f"validation: {error.message}\n"
                    "Return a complete replacement JSON response. Preserve transcript "
                    "grounding and source ranges while correcting the validation error. "
                    "Recheck every candidate against the entire explanation ladder, not "
                    "only the reported error. Do not add external facts.\n"
                    f"Previous response:\n{raw}"
                )

        raise AssertionError("candidate generation retry loop exhausted")

    async def generate_keyword_categories(
        self,
        occurrences: list[dict[str, Any]],
        target_language: str,
        options: dict[str, Any],
    ) -> list[dict[str, Any]]:
        occurrence_ids = [item["keywordId"] for item in occurrences]
        system, user = category_grouping_prompt(
            json.dumps(occurrences, ensure_ascii=False), target_language
        )
        raw = await self._generate(system, user, options, CATEGORY_GROUPING_SCHEMA)
        return validate_category_grouping(
            parse_json_object(raw, "LLM_CATEGORY_GROUPING_INVALID_JSON"),
            occurrence_ids,
        )

    async def plan_explanation_enrichment(
        self,
        contexts: list[EnrichmentContext],
        target_language: str,
        options: dict[str, Any],
    ) -> list[EnrichmentPlan]:
        system, user = enrichment_plan_prompt(contexts, target_language)
        raw = await self._generate(system, user, options, ENRICHMENT_PLAN_SCHEMA)
        return validate_plan_payload(
            parse_json_object(raw, "LLM_ENRICHMENT_PLAN_INVALID_JSON"), contexts
        )

    async def synthesize_explanation_enrichment(
        self,
        context: EnrichmentContext,
        plan: EnrichmentPlan,
        evidence: ResearchEvidence,
        target_language: str,
        options: dict[str, Any],
    ) -> OccurrenceEnrichment:
        system, user = enrichment_synthesis_prompt(
            context, plan, evidence, target_language
        )
        raw = await self._generate(system, user, options, ENRICHMENT_SYNTHESIS_SCHEMA)
        return validate_synthesis_payload(
            parse_json_object(raw, "LLM_ENRICHMENT_SYNTHESIS_INVALID_JSON"),
            context,
            evidence,
        )

    async def review_explanation_enrichment(
        self,
        context: EnrichmentContext,
        enrichment: OccurrenceEnrichment,
        evidence: ResearchEvidence,
        target_language: str,
        options: dict[str, Any],
    ) -> bool:
        system, user = enrichment_review_prompt(
            context, enrichment, evidence, target_language
        )
        raw = await self._generate(system, user, options, ENRICHMENT_REVIEW_SCHEMA)
        payload = parse_json_object(raw, "LLM_ENRICHMENT_REVIEW_INVALID_JSON")
        if (
            set(payload) != {"approved", "reasonCode"}
            or not isinstance(payload["approved"], bool)
            or not isinstance(payload["reasonCode"], str)
            or not payload["reasonCode"].strip()
        ):
            raise AppError(
                502,
                "LLM_ENRICHMENT_REVIEW_INVALID_JSON",
                "Review payload must contain approved and reasonCode",
            )
        return payload["approved"]

    async def _generate(
        self,
        system: str,
        user: str,
        options: dict[str, Any],
        schema: dict[str, Any],
    ) -> str:
        provider = options["provider"]
        if self.client:
            return await self._generate_with_client(self.client, provider, system, user, options, schema)
        async with httpx.AsyncClient(timeout=120) as client:
            return await self._generate_with_client(client, provider, system, user, options, schema)

    async def _generate_with_client(self, client: httpx.AsyncClient, provider: str, system: str, user: str, options: dict[str, Any], schema: dict[str, Any]) -> str:
        if provider == "openai":
            return await self._openai(client, system, user, options, schema)
        if provider == "gemini":
            return await self._gemini(client, system, user, options)
        return await self._claude(client, system, user, options)

    async def _openai(self, client: httpx.AsyncClient, system: str, user: str, options: dict[str, Any], schema: dict[str, Any]) -> str:
        key = self._api_key("openai")
        response = await client.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": options["model"],
                "temperature": options["temperature"],
                **({"max_output_tokens": options["maxOutputTokens"]} if options.get("maxOutputTokens") else {}),
                "input": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": schema["name"],
                        "schema": schema["schema"],
                        "strict": schema["strict"],
                    }
                },
            },
        )
        payload = _response_json(response)
        if not response.is_success:
            error = payload.get("error", {}) if isinstance(payload, dict) else {}
            code = error.get("code")
            mapped = (
                "LLM_AUTH_ERROR" if response.status_code == 401 or code == "invalid_api_key"
                else "LLM_QUOTA_OR_RATE_LIMIT" if response.status_code == 429 or code in {"insufficient_quota", "rate_limit_exceeded"}
                else "LLM_CONTEXT_LENGTH_EXCEEDED" if code == "context_length_exceeded"
                else "LLM_REQUEST_FAILED"
            )
            raise AppError(502, mapped, error.get("message", "OpenAI request failed"))
        if payload.get("status") == "incomplete":
            raise AppError(502, "LLM_RESPONSE_INCOMPLETE", "OpenAI returned an incomplete response")
        if payload.get("status") == "failed":
            raise AppError(502, "LLM_REQUEST_FAILED", "OpenAI response failed")
        output_text = payload.get("output_text", "")
        if not output_text:
            output_text = "".join(
                part.get("text", "")
                for item in payload.get("output", [])
                for part in item.get("content", [])
                if isinstance(part, dict)
            )
        return _require_output(output_text, "OpenAI")

    async def _gemini(self, client: httpx.AsyncClient, system: str, user: str, options: dict[str, Any]) -> str:
        response = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{options['model']}:generateContent",
            params={"key": self._api_key("gemini")},
            json={
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": {
                    "temperature": options["temperature"],
                    "responseMimeType": "application/json",
                    **({"maxOutputTokens": options["maxOutputTokens"]} if options.get("maxOutputTokens") else {}),
                },
            },
        )
        payload = _response_json(response)
        if not response.is_success:
            raise AppError(502, "LLM_REQUEST_FAILED", payload.get("error", {}).get("message", "Gemini request failed"))
        text = "".join(
            part.get("text", "")
            for candidate in payload.get("candidates", [])[:1]
            for part in candidate.get("content", {}).get("parts", [])
        )
        return _require_output(text, "Gemini")

    async def _claude(self, client: httpx.AsyncClient, system: str, user: str, options: dict[str, Any]) -> str:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self._api_key("claude"),
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": options["model"],
                "temperature": options["temperature"],
                "max_tokens": options.get("maxOutputTokens", 3000),
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
        )
        payload = _response_json(response)
        if not response.is_success:
            raise AppError(502, "LLM_REQUEST_FAILED", payload.get("error", {}).get("message", "Claude request failed"))
        text = "".join(part.get("text", "") for part in payload.get("content", []))
        return _require_output(text, "Claude")

    def _api_key(self, provider: str) -> str:
        key = {
            "openai": self.settings.openai_api_key,
            "gemini": self.settings.gemini_api_key,
            "claude": self.settings.anthropic_api_key,
        }[provider].strip()
        if not key:
            env_name = {"openai": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY", "claude": "ANTHROPIC_API_KEY"}[provider]
            raise AppError(500, "LLM_PROVIDER_NOT_CONFIGURED", f"{env_name} is required for provider '{provider}'")
        return key


def validate_candidate(value: Any, index: int, chunk_labels: list[str]) -> dict[str, Any]:
    required_strings = (
        "kind", "title", "text", "brief", "simpleExplanation",
        "contextualExplanation", "detailedExplanation", "signalLevel",
    )
    if not isinstance(value, dict) or not all(isinstance(value.get(key), str) for key in required_strings):
        raise AppError(502, "LLM_CLIPPINGS_INVALID_JSON", f"Invalid candidate clipping fields at index {index}")
    cleaned = {key: item.strip() if isinstance(item, str) else item for key, item in value.items()}
    errors: list[tuple[str, str]] = []
    if cleaned["kind"] not in {
        "topic", "claim", "mechanism", "risk", "trend",
        "entity", "example", "question", "contradiction",
    }:
        errors.append(("LLM_CLIPPINGS_INVALID_JSON", "Invalid candidate kind"))
    if cleaned["signalLevel"] not in {"high", "medium", "low"}:
        errors.append(("LLM_CLIPPINGS_INVALID_JSON", "Invalid signal level"))
    if not 3 <= len(cleaned["text"]) <= 500:
        errors.append(
            ("LLM_CLIPPINGS_INVALID_JSON", "Candidate text must contain 3-500 characters")
        )
    errors.extend(
        ("LLM_CLIPPINGS_INVALID_JSON", message)
        for message in explanation_ladder_errors(
            cleaned["title"],
            cleaned["brief"],
            cleaned["simpleExplanation"],
            cleaned["contextualExplanation"],
            cleaned["detailedExplanation"],
        )
    )
    refs = cleaned.get("sourceRefs")
    validated_refs = []
    if not isinstance(refs, list) or not refs:
        errors.append(("LLM_CLIPPINGS_INVALID_JSON", "Source refs must be non-empty"))
    else:
        order = {
            normalize_segment_ref(label): position
            for position, label in enumerate(chunk_labels)
        }
        for source_index, ref in enumerate(refs):
            if not isinstance(ref, dict) or not all(
                isinstance(ref.get(key), str)
                for key in ("startSegmentId", "endSegmentId", "timestamp", "text")
            ):
                errors.append(
                    (
                        "LLM_CLIPPINGS_INVALID_JSON",
                        f"Source ref {source_index} has invalid fields",
                    )
                )
                continue
            start_label = ref["startSegmentId"].strip()
            end_label = ref["endSegmentId"].strip()
            start = order.get(normalize_segment_ref(start_label))
            end = order.get(normalize_segment_ref(end_label))
            if start is None or end is None or start > end:
                errors.append(
                    (
                        "LLM_CLIPPINGS_INVALID_SOURCE_REF",
                        f"Source ref {source_index} is outside the topic chunk",
                    )
                )
                continue
            source_text = ref["text"].strip()
            if not 3 <= len(source_text) <= 300:
                errors.append(
                    (
                        "LLM_CLIPPINGS_INVALID_JSON",
                        f"Source ref {source_index} text must contain 3-300 characters",
                    )
                )
                continue
            validated_refs.append({
                "startSegmentId": chunk_labels[start],
                "endSegmentId": chunk_labels[end],
                "timestamp": ref["timestamp"].strip(),
                "text": source_text,
            })
    if errors:
        error_code = (
            "LLM_CLIPPINGS_INVALID_SOURCE_REF"
            if all(code == "LLM_CLIPPINGS_INVALID_SOURCE_REF" for code, _ in errors)
            else "LLM_CLIPPINGS_INVALID_JSON"
        )
        raise AppError(502, error_code, "; ".join(message for _, message in errors))
    cleaned["sourceRefs"] = validated_refs
    return cleaned


def validate_candidates(
    candidates: list[Any], chunk_labels: list[str]
) -> list[dict[str, Any]]:
    validated: list[dict[str, Any]] = []
    errors: list[tuple[str, str]] = []
    for index, candidate in enumerate(candidates):
        try:
            validated.append(validate_candidate(candidate, index, chunk_labels))
        except AppError as error:
            title = candidate.get("title") if isinstance(candidate, dict) else None
            label = f'Candidate {index} "{title}"' if isinstance(title, str) else f"Candidate {index}"
            errors.append((error.code, f"{label}: {error.message}"))
    if errors:
        error_code = (
            "LLM_CLIPPINGS_INVALID_SOURCE_REF"
            if all(code == "LLM_CLIPPINGS_INVALID_SOURCE_REF" for code, _ in errors)
            else "LLM_CLIPPINGS_INVALID_JSON"
        )
        raise AppError(502, error_code, " | ".join(message for _, message in errors))
    return validated


def validate_category_grouping(
    value: Any, occurrence_ids: list[str]
) -> list[dict[str, Any]]:
    if not isinstance(value, dict) or set(value) != {"categories"}:
        raise AppError(502, "LLM_CATEGORY_GROUPING_INVALID_JSON", "Invalid category grouping object")
    categories = value["categories"]
    if not isinstance(categories, list) or not categories:
        raise AppError(502, "LLM_CATEGORY_GROUPING_INVALID_JSON", "Categories must be non-empty")

    known = set(occurrence_ids)
    assigned: list[str] = []
    normalized_titles: set[str] = set()
    cleaned_categories: list[dict[str, Any]] = []
    for index, category in enumerate(categories):
        if not isinstance(category, dict) or set(category) != {"title", "keywordIds"}:
            raise AppError(502, "LLM_CATEGORY_GROUPING_INVALID_JSON", f"Invalid category at index {index}")
        title, keyword_ids = category["title"], category["keywordIds"]
        if not isinstance(title, str) or not 2 <= len(title.strip()) <= 80:
            raise AppError(502, "LLM_CATEGORY_GROUPING_INVALID_JSON", "Category titles must contain 2-80 characters")
        if not isinstance(keyword_ids, list) or not keyword_ids:
            raise AppError(502, "LLM_CATEGORY_GROUPING_INVALID_JSON", "Category keyword IDs must be non-empty")
        if not all(isinstance(item, str) and item for item in keyword_ids):
            raise AppError(502, "LLM_CATEGORY_GROUPING_INVALID_JSON", "Category keyword IDs must be strings")
        normalized_title = re.sub(r"\s+", " ", title).strip().casefold()
        if normalized_title in normalized_titles:
            raise AppError(502, "LLM_CATEGORY_GROUPING_INVALID_JSON", "Category titles must be unique")
        normalized_titles.add(normalized_title)
        unknown = next((item for item in keyword_ids if item not in known), None)
        if unknown:
            raise AppError(502, "LLM_CATEGORY_GROUPING_INVALID_JSON", f"Category contains unknown occurrence ID: {unknown}")
        assigned.extend(keyword_ids)
        cleaned_categories.append({"title": title.strip(), "keywordIds": keyword_ids})

    if len(assigned) != len(occurrence_ids) or set(assigned) != known:
        raise AppError(502, "LLM_CATEGORY_GROUPING_INVALID_JSON", "Every occurrence ID must be assigned exactly once")
    return cleaned_categories


def normalize_segment_ref(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    return str(int(digits)) if digits else value


def parse_json_object(raw: str, code: str) -> dict[str, Any]:
    normalized = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.IGNORECASE)
    try:
        value = json.loads(normalized)
    except json.JSONDecodeError as error:
        raise AppError(502, code, "Model returned invalid JSON") from error
    if not isinstance(value, dict):
        raise AppError(502, code, "Model returned invalid JSON object")
    return value


def _response_json(response: httpx.Response) -> dict[str, Any]:
    try:
        value = response.json()
    except ValueError:
        value = {}
    return value if isinstance(value, dict) else {}


def _require_output(value: Any, provider: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AppError(502, "LLM_EMPTY_OUTPUT", f"{provider} returned empty output")
    return value.strip()
