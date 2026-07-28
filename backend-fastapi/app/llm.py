import json
import re
from typing import Any

import httpx

from app.config import Settings
from app.errors import AppError
from app.prompts import (
    CANDIDATE_CLIPPING_SCHEMA,
    TOPIC_CHUNKING_SCHEMA,
    candidate_clipping_prompt,
    topic_chunking_prompt,
)

PROVIDERS = {"openai", "gemini", "claude"}
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
        raw = await self._generate(system, user, options, CANDIDATE_CLIPPING_SCHEMA)
        payload = parse_json_object(raw, "LLM_CLIPPINGS_INVALID_JSON")
        candidates = payload.get("candidateClippings")
        if not isinstance(candidates, list):
            raise AppError(502, "LLM_CLIPPINGS_INVALID_JSON", "Invalid candidate clipping list")
        labels = [
            match.group(1)
            for line in segments.splitlines()
            if (match := re.match(r"^\s*([^|\s]+)\s*\|", line))
        ]
        return [validate_candidate(value, index, labels) for index, value in enumerate(candidates)]

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
    if value["signalLevel"] not in {"high", "medium", "low"}:
        raise AppError(502, "LLM_CLIPPINGS_INVALID_JSON", f"Invalid candidate clipping fields at index {index}")
    cleaned = {key: item.strip() if isinstance(item, str) else item for key, item in value.items()}
    validate_explanation_ladder(
        cleaned["title"],
        cleaned["brief"],
        cleaned["simpleExplanation"],
        cleaned["contextualExplanation"],
        cleaned["detailedExplanation"],
    )
    refs = cleaned.get("sourceRefs")
    if not isinstance(refs, list) or not refs:
        raise AppError(502, "LLM_CLIPPINGS_INVALID_JSON", f"Invalid source refs at candidate {index}")
    order = {normalize_segment_ref(label): position for position, label in enumerate(chunk_labels)}
    validated_refs = []
    for source_index, ref in enumerate(refs):
        if not isinstance(ref, dict) or not all(
            isinstance(ref.get(key), str)
            for key in ("startSegmentId", "endSegmentId", "timestamp", "text")
        ):
            raise AppError(502, "LLM_CLIPPINGS_INVALID_JSON", f"Invalid source ref at candidate {index}, source {source_index}")
        start_label, end_label = ref["startSegmentId"].strip(), ref["endSegmentId"].strip()
        start, end = order.get(normalize_segment_ref(start_label)), order.get(normalize_segment_ref(end_label))
        if start is None or end is None or start > end:
            raise AppError(502, "LLM_CLIPPINGS_INVALID_SOURCE_REF", f"Source ref outside topic chunk at candidate {index}, source {source_index}")
        validated_refs.append({
            "startSegmentId": chunk_labels[start],
            "endSegmentId": chunk_labels[end],
            "timestamp": ref["timestamp"].strip(),
            "text": ref["text"].strip(),
        })
    cleaned["sourceRefs"] = validated_refs
    return cleaned


def validate_explanation_ladder(term: str, brief: str, simple: str, contextual: str, detailed: str) -> None:
    if any(not value.strip() for value in (term, brief, simple, contextual, detailed)):
        raise AppError(502, "LLM_CLIPPINGS_INVALID_JSON", "Explanation ladder fields must not be empty")
    levels = [normalize_explanation(value) for value in (simple, contextual, detailed)]
    if len(set(levels)) != 3:
        raise AppError(502, "LLM_CLIPPINGS_INVALID_JSON", "Explanation ladder levels must not be duplicates")
    if len(term) > 60:
        raise AppError(502, "LLM_CLIPPINGS_INVALID_JSON", "Term must be at most 60 characters")
    if re.search(r"[.!?。！？]\s*$", term):
        raise AppError(502, "LLM_CLIPPINGS_INVALID_JSON", "Term must be a reusable label, not a sentence")
    brief_words = len(brief.split())
    if " " in brief and (brief_words < 5 or brief_words > 10):
        raise AppError(502, "LLM_CLIPPINGS_INVALID_JSON", "Brief must contain 5-10 words")
    if " " not in brief and not 5 <= len(brief) <= 40:
        raise AppError(502, "LLM_CLIPPINGS_INVALID_JSON", "Brief must contain 5-40 characters")
    if len(brief) >= len(simple):
        raise AppError(502, "LLM_CLIPPINGS_INVALID_JSON", "Brief must be shorter than simple explanation")
    if sentence_count(simple) != 1:
        raise AppError(502, "LLM_CLIPPINGS_INVALID_JSON", "Simple explanation must be one sentence")
    if sentence_count(contextual) not in {2, 3} or len(simple) >= len(contextual):
        raise AppError(502, "LLM_CLIPPINGS_INVALID_JSON", "Contextual explanation must be 2-3 sentences and add detail")
    if sentence_count(detailed) not in {3, 4, 5} or len(contextual) >= len(detailed):
        raise AppError(502, "LLM_CLIPPINGS_INVALID_JSON", "Detailed explanation must be 3-5 sentences and add detail")


def sentence_count(value: str) -> int:
    parts = [part for part in re.split(r"[.!?。！？]+(?:[\"')\]]*)\s*", value.strip()) if part.strip()]
    return max(1, len(parts))


def normalize_explanation(value: str) -> str:
    return re.sub(r"[.?!。！？]+$", "", re.sub(r"\s+", " ", value.lower()).strip())


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
