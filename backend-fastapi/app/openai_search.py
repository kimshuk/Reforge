import json
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

from app.config import Settings
from app.enrichment import EnrichmentContext, EnrichmentPlan, ResearchEvidence, ResearchSource
from app.errors import AppError

SEARCH_SYSTEM_PROMPT = """Research only the supplied contextual keyword occurrence.
Return a concise factual answer that can clarify the supplied transcript explanation.
Prefer the requested source class when possible. Do not combine separate occurrences,
replace the speaker's claim, or introduce unsupported conclusions."""


def occurrence_research_prompt(
    context: EnrichmentContext, plan: EnrichmentPlan
) -> str:
    return json.dumps(
        {
            "keywordId": context.keyword_id,
            "term": context.term,
            "kind": context.kind,
            "chunkTitle": context.chunk_title,
            "chunkSummary": context.chunk_summary,
            "sourceExcerpts": list(context.source_excerpts),
            "transcriptLevel2": context.transcript_level2,
            "transcriptLevel3": context.transcript_level3,
            "researchQuestion": plan.research_question,
            "preferredSourceClass": plan.preferred_source_class,
        },
        ensure_ascii=False,
    )


class OpenAIWebSearchClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self.client = client

    async def research_occurrence(
        self,
        context: EnrichmentContext,
        plan: EnrichmentPlan,
        options: dict[str, Any],
    ) -> ResearchEvidence:
        if self.client is not None:
            return await self._research_with_client(self.client, context, plan, options)
        async with httpx.AsyncClient(timeout=120) as client:
            return await self._research_with_client(client, context, plan, options)

    async def _research_with_client(
        self,
        client: httpx.AsyncClient,
        context: EnrichmentContext,
        plan: EnrichmentPlan,
        options: dict[str, Any],
    ) -> ResearchEvidence:
        try:
            response = await client.post(
                "https://api.openai.com/v1/responses",
                headers={"Authorization": f"Bearer {self._api_key()}"},
                json={
                    "model": options["model"],
                    "tools": [{"type": "web_search", "search_context_size": "medium"}],
                    "tool_choice": "auto",
                    "input": [
                        {"role": "system", "content": SEARCH_SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": occurrence_research_prompt(context, plan),
                        },
                    ],
                },
            )
        except httpx.HTTPError as error:
            raise AppError(502, "LLM_REQUEST_FAILED", "OpenAI web search request failed") from error

        payload = _response_json(response)
        if not response.is_success:
            _raise_provider_error(response.status_code, payload)
        if payload.get("status") == "incomplete":
            raise AppError(502, "LLM_RESPONSE_INCOMPLETE", "OpenAI returned an incomplete response")
        if payload.get("status") == "failed":
            raise AppError(502, "LLM_REQUEST_FAILED", "OpenAI web search response failed")
        if payload.get("status") != "completed":
            raise AppError(
                502,
                "LLM_WEB_SEARCH_INVALID_RESPONSE",
                "OpenAI web search response has an invalid status",
            )
        return _extract_evidence(payload, self.settings.explanation_enrichment_max_sources)

    def _api_key(self) -> str:
        key = self.settings.openai_api_key.strip()
        if not key:
            raise AppError(
                500,
                "LLM_PROVIDER_NOT_CONFIGURED",
                "OPENAI_API_KEY is required for OpenAI web search",
            )
        return key


def _extract_evidence(payload: dict[str, Any], max_sources: int) -> ResearchEvidence:
    output = payload.get("output")
    if not isinstance(output, list):
        raise AppError(
            502,
            "LLM_WEB_SEARCH_INVALID_RESPONSE",
            "OpenAI web search response must include output",
        )

    summary_parts: list[str] = []
    sources: list[ResearchSource] = []
    seen_urls: set[str] = set()
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            raise AppError(
                502,
                "LLM_WEB_SEARCH_INVALID_RESPONSE",
                "OpenAI message output must include content",
            )
        for part in content:
            if not isinstance(part, dict) or part.get("type") != "output_text":
                continue
            text = part.get("text")
            annotations = part.get("annotations", [])
            if not isinstance(text, str) or not isinstance(annotations, list):
                raise AppError(
                    502,
                    "LLM_WEB_SEARCH_INVALID_RESPONSE",
                    "OpenAI output text is malformed",
                )
            if text.strip():
                summary_parts.append(text.strip())
            for annotation in annotations:
                source = _citation_source(annotation, text)
                if source is None:
                    continue
                if source.url in seen_urls:
                    continue
                seen_urls.add(source.url)
                if len(sources) < max_sources:
                    sources.append(
                        ResearchSource(
                            citation_id=f"C{len(sources) + 1}",
                            title=source.title,
                            url=source.url,
                            supporting_text=source.supporting_text,
                        )
                    )

    return ResearchEvidence(summary="\n".join(summary_parts), sources=tuple(sources))


def _citation_source(annotation: Any, text: str) -> ResearchSource | None:
    if not isinstance(annotation, dict):
        raise AppError(
            502,
            "LLM_WEB_SEARCH_INVALID_RESPONSE",
            "OpenAI output annotation is malformed",
        )
    if annotation.get("type") != "url_citation":
        return None

    start_index = annotation.get("start_index")
    end_index = annotation.get("end_index")
    title = annotation.get("title")
    if (
        isinstance(start_index, bool)
        or isinstance(end_index, bool)
        or not isinstance(start_index, int)
        or not isinstance(end_index, int)
        or start_index < 0
        or end_index <= start_index
        or end_index > len(text)
        or not isinstance(title, str)
        or not title.strip()
    ):
        raise AppError(
            502,
            "LLM_WEB_SEARCH_INVALID_RESPONSE",
            "OpenAI URL citation annotation has invalid bounds or metadata",
        )

    supporting_text = text[start_index:end_index].strip()
    if not supporting_text:
        raise AppError(
            502,
            "LLM_WEB_SEARCH_INVALID_RESPONSE",
            "OpenAI URL citation annotation has empty supporting text",
        )
    url = _normalize_url(annotation.get("url"))
    return ResearchSource(
        citation_id="",
        title=title.strip(),
        url=url,
        supporting_text=supporting_text,
    )


def _normalize_url(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AppError(
            502,
            "LLM_WEB_SEARCH_INVALID_RESPONSE",
            "OpenAI URL citation annotation has an invalid URL",
        )
    try:
        parsed = urlsplit(value.strip())
        if (
            parsed.scheme.lower() not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise ValueError
        port = parsed.port
    except ValueError as error:
        raise AppError(
            502,
            "LLM_WEB_SEARCH_INVALID_RESPONSE",
            "OpenAI URL citation annotation has an invalid URL",
        ) from error

    scheme = parsed.scheme.lower()
    hostname = parsed.hostname.lower()
    netloc = f"[{hostname}]" if ":" in hostname else hostname
    if port is not None and (scheme, port) not in {("http", 80), ("https", 443)}:
        netloc = f"{netloc}:{port}"
    path = parsed.path or "/"
    return urlunsplit((scheme, netloc, path, parsed.query, ""))


def _raise_provider_error(status_code: int, payload: dict[str, Any]) -> None:
    error = payload.get("error", {}) if isinstance(payload, dict) else {}
    code = error.get("code") if isinstance(error, dict) else None
    message = error.get("message") if isinstance(error, dict) else None
    mapped = (
        "LLM_AUTH_ERROR"
        if status_code == 401 or code == "invalid_api_key"
        else "LLM_QUOTA_OR_RATE_LIMIT"
        if status_code == 429 or code in {"insufficient_quota", "rate_limit_exceeded"}
        else "LLM_CONTEXT_LENGTH_EXCEEDED"
        if code == "context_length_exceeded"
        else "LLM_REQUEST_FAILED"
    )
    raise AppError(502, mapped, message if isinstance(message, str) else "OpenAI web search request failed")


def _response_json(response: httpx.Response) -> dict[str, Any]:
    try:
        value = response.json()
    except ValueError:
        value = {}
    return value if isinstance(value, dict) else {}
