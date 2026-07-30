import copy
import json
from typing import Any

import httpx
import pytest

from app.config import Settings
from app.enrichment import EnrichmentContext, EnrichmentPlan
from app.errors import AppError
from app.openai_search import (
    SEARCH_SYSTEM_PROMPT,
    OpenAIWebSearchClient,
    occurrence_research_prompt,
)

RESPONSE = {
    "status": "completed",
    "output": [
        {
            "type": "web_search_call",
            "id": "ws_1",
            "status": "completed",
            "action": {
                "sources": [
                    {"url": "https://example.com/uncited-search-call-source"}
                ]
            },
        },
        {
            "type": "message",
            "content": [
                {
                    "type": "output_text",
                    "text": "Codex documentation describes delegated coding tasks.",
                    "annotations": [
                        {
                            "type": "url_citation",
                            "start_index": 0,
                            "end_index": 53,
                            "title": "OpenAI Codex documentation",
                            "url": "https://platform.openai.com/docs/codex",
                        }
                    ],
                }
            ],
        },
    ],
}

OPTIONS = {
    "provider": "openai",
    "model": "gpt-4o-mini",
    "temperature": 0.2,
}


def context() -> EnrichmentContext:
    return EnrichmentContext(
        keyword_id="K001",
        term="Codex",
        kind="entity",
        brief="An autonomous coding tool from OpenAI",
        simple_explanation="Codex is an AI system that helps people write software.",
        chunk_title="Coding agents",
        chunk_summary="The speaker introduces Codex as an autonomous coding tool.",
        source_excerpts=("Codex can handle delegated coding tasks.",),
        transcript_level2=(
            "The speaker introduces Codex as a coding tool. It is presented as useful for delegated tasks."
        ),
        transcript_level3=(
            "The speaker introduces Codex as a coding tool. It can take delegated tasks from a user. "
            "That changes how the speaker frames software work. The example focuses on coding tasks."
        ),
        video_topic_outline=("AI coding tools",),
    )


def plan() -> EnrichmentPlan:
    return EnrichmentPlan(
        keyword_id="K001",
        level2=(
            "The speaker introduces Codex as a coding tool. It is presented as useful for delegated tasks."
        ),
        level3=(
            "The speaker introduces Codex as a coding tool. It can take delegated tasks from a user. "
            "That changes how the speaker frames software work. The example focuses on coding tasks."
        ),
        needs_external_research=True,
        research_question="What does Codex documentation say about delegated coding tasks?",
        preferred_source_class="official",
    )


def client_for(payload: dict[str, Any], status_code: int = 200) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(status_code, json=payload)
        )
    )


@pytest.mark.asyncio
async def test_research_extracts_cited_support_and_uses_expected_request() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=RESPONSE)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        search = OpenAIWebSearchClient(Settings(openai_api_key="test-key"), client)
        evidence = await search.research_occurrence(context(), plan(), OPTIONS)

    assert evidence.summary == "Codex documentation describes delegated coding tasks."
    assert evidence.sources[0].citation_id == "C1"
    assert evidence.sources[0].title == "OpenAI Codex documentation"
    assert evidence.sources[0].url == "https://platform.openai.com/docs/codex"
    assert evidence.sources[0].supporting_text == (
        "Codex documentation describes delegated coding tasks."
    )
    assert len(evidence.sources) == 1
    assert requests[0].url == "https://api.openai.com/v1/responses"
    assert requests[0].headers["Authorization"] == "Bearer test-key"
    assert json.loads(requests[0].content) == {
        "model": "gpt-4o-mini",
        "tools": [{"type": "web_search", "search_context_size": "medium"}],
        "tool_choice": "auto",
        "input": [
            {
                "role": "system",
                "content": SEARCH_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": occurrence_research_prompt(context(), plan()),
            },
        ],
    }


@pytest.mark.asyncio
async def test_research_normalizes_urls_deduplicates_and_limits_to_three() -> None:
    payload = copy.deepcopy(RESPONSE)
    output = payload["output"][-1]["content"][0]
    text = "One. Two. Three. Four."
    output["text"] = text
    output["annotations"] = [
        {
            "type": "url_citation",
            "start_index": 0,
            "end_index": 4,
            "title": "First source",
            "url": "HTTPS://Example.com:443/one#fragment",
        },
        {
            "type": "url_citation",
            "start_index": 5,
            "end_index": 9,
            "title": "Duplicate source",
            "url": "https://example.com/one",
        },
        {
            "type": "url_citation",
            "start_index": 10,
            "end_index": 16,
            "title": "Second source",
            "url": "https://example.com/two",
        },
        {
            "type": "url_citation",
            "start_index": 17,
            "end_index": 22,
            "title": "Third source",
            "url": "https://example.com/three",
        },
        {
            "type": "url_citation",
            "start_index": 0,
            "end_index": 4,
            "title": "Fourth source",
            "url": "https://example.com/four",
        },
    ]

    async with client_for(payload) as client:
        search = OpenAIWebSearchClient(Settings(openai_api_key="test-key"), client)
        evidence = await search.research_occurrence(context(), plan(), OPTIONS)

    assert [(source.citation_id, source.url) for source in evidence.sources] == [
        ("C1", "https://example.com/one"),
        ("C2", "https://example.com/two"),
        ("C3", "https://example.com/three"),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "annotation",
    [
        {
            "type": "url_citation",
            "start_index": 0,
            "end_index": 54,
            "title": "Out of bounds",
            "url": "https://example.com/source",
        },
        {
            "type": "url_citation",
            "start_index": 2,
            "end_index": 2,
            "title": "Empty range",
            "url": "https://example.com/source",
        },
        {
            "type": "url_citation",
            "start_index": "0",
            "end_index": 5,
            "title": "Invalid index",
            "url": "https://example.com/source",
        },
        {
            "type": "url_citation",
            "start_index": 0,
            "end_index": 5,
            "title": "Missing URL",
            "url": "not-a-url",
        },
    ],
)
async def test_research_rejects_malformed_url_citation_annotations(
    annotation: dict[str, Any],
) -> None:
    payload = copy.deepcopy(RESPONSE)
    payload["output"][-1]["content"][0]["annotations"] = [annotation]

    async with client_for(payload) as client:
        search = OpenAIWebSearchClient(Settings(openai_api_key="test-key"), client)
        with pytest.raises(AppError) as raised:
            await search.research_occurrence(context(), plan(), OPTIONS)

    assert raised.value.code == "LLM_WEB_SEARCH_INVALID_RESPONSE"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "payload", "code"),
    [
        (401, {"error": {"code": "invalid_api_key", "message": "No key"}}, "LLM_AUTH_ERROR"),
        (429, {"error": {"code": "rate_limit_exceeded", "message": "Slow down"}}, "LLM_QUOTA_OR_RATE_LIMIT"),
        (500, {"error": {"message": "Upstream failed"}}, "LLM_REQUEST_FAILED"),
        (200, {"status": "incomplete"}, "LLM_RESPONSE_INCOMPLETE"),
        (200, {"status": "failed"}, "LLM_REQUEST_FAILED"),
    ],
)
async def test_research_maps_provider_errors_to_app_errors(
    status_code: int, payload: dict[str, Any], code: str
) -> None:
    async with client_for(payload, status_code=status_code) as client:
        search = OpenAIWebSearchClient(Settings(openai_api_key="test-key"), client)
        with pytest.raises(AppError) as raised:
            await search.research_occurrence(context(), plan(), OPTIONS)

    assert raised.value.code == code
