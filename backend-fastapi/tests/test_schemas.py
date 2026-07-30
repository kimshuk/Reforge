import pytest

from app.config import Settings
from app.errors import AppError
from app.llm import resolve_llm_options
from app.schemas import AnalyzeKeyword, normalize_target_language, parse_analyze_request


def test_keyword_citation_fields_default_to_empty_arrays() -> None:
    keyword = AnalyzeKeyword.model_validate(
        {
            "term": "Codex",
            "candidateClippingId": "occurrence-1",
            "brief": "An autonomous coding system from OpenAI",
            "level1": "Codex is an AI system that performs coding tasks.",
            "level2": "The speaker introduces Codex as an autonomous tool. They explain the work it performs.",
            "level3": "The speaker introduces Codex as an autonomous tool. They describe concrete coding work it can perform. This explains why it matters in the section.",
            "source": {"type": "youtube", "ref": "https://example.com?t=46s"},
            "sources": [{"type": "youtube", "ref": "https://example.com?t=46s"}],
        }
    )

    assert keyword.level2CitationIds == []
    assert keyword.level3CitationIds == []
    assert keyword.externalSources == []


def test_rejects_more_than_three_external_sources() -> None:
    with pytest.raises(ValueError):
        AnalyzeKeyword.model_validate(
            {
                "term": "Codex",
                "candidateClippingId": "occurrence-1",
                "brief": "An autonomous coding system from OpenAI",
                "level1": "Codex is an AI system that performs coding tasks.",
                "level2": "The speaker introduces Codex as an autonomous tool. They explain the work it performs.",
                "level3": "The speaker introduces Codex as an autonomous tool. They describe concrete coding work it can perform. This explains why it matters in the section.",
                "source": {"type": "youtube", "ref": "https://example.com?t=46s"},
                "sources": [{"type": "youtube", "ref": "https://example.com?t=46s"}],
                "externalSources": [
                    {"citationId": f"source-{index}", "title": "Source", "url": "https://example.com"}
                    for index in range(4)
                ],
            }
        )


def test_rejects_duplicate_external_source_citation_ids() -> None:
    with pytest.raises(ValueError):
        AnalyzeKeyword.model_validate(
            {
                "term": "Codex",
                "candidateClippingId": "occurrence-1",
                "brief": "An autonomous coding system from OpenAI",
                "level1": "Codex is an AI system that performs coding tasks.",
                "level2": "The speaker introduces Codex as an autonomous tool. They explain the work it performs.",
                "level3": "The speaker introduces Codex as an autonomous tool. They describe concrete coding work it can perform. This explains why it matters in the section.",
                "source": {"type": "youtube", "ref": "https://example.com?t=46s"},
                "sources": [{"type": "youtube", "ref": "https://example.com?t=46s"}],
                "externalSources": [
                    {"citationId": "source-1", "title": "First", "url": "https://one.example.com"},
                    {"citationId": "source-1", "title": "Second", "url": "https://two.example.com"},
                ],
            }
        )


def test_enrichment_is_disabled_and_bounded_by_default() -> None:
    settings = Settings()

    assert settings.explanation_enrichment_enabled is False
    assert settings.explanation_enrichment_max_sources == 3
    assert settings.explanation_enrichment_max_concurrency == 3


@pytest.mark.parametrize(
    "values",
    [
        {"explanation_enrichment_max_sources": 4},
        {"explanation_enrichment_max_concurrency": 0},
    ],
)
def test_rejects_unsafe_enrichment_limits(values: dict[str, int]) -> None:
    with pytest.raises(ValueError):
        Settings(**values)


def test_parses_manual_request_and_normalizes_language() -> None:
    source = parse_analyze_request(
        {"type": "manual", "text": "a useful transcript", "targetLanguage": "ko-kr"},
        Settings(),
    )

    assert source.type == "manual"
    assert source.text == "a useful transcript"
    assert source.target_language == "ko-KR"


def test_rejects_unknown_fields_and_disabled_overrides() -> None:
    with pytest.raises(AppError, match="Unsupported request field: provider"):
        parse_analyze_request(
            {"type": "manual", "text": "transcript", "provider": "claude"},
            Settings(allow_analyze_llm_overrides=False),
        )


def test_rejects_invalid_language() -> None:
    with pytest.raises(AppError) as raised:
        normalize_target_language("not_a_language")

    assert raised.value.code == "INVALID_TARGET_LANGUAGE"


@pytest.mark.parametrize(
    ("provider", "model"),
    [
        ("openai", "gpt-4o-mini"),
        ("gemini", "gemini-1.5-flash"),
        ("claude", "claude-3-5-haiku-latest"),
    ],
)
def test_provider_uses_its_default_model(provider: str, model: str) -> None:
    source = parse_analyze_request(
        {"type": "manual", "text": "transcript", "provider": provider},
        Settings(allow_analyze_llm_overrides=True, llm_provider="openai", llm_model=None),
    )

    assert resolve_llm_options(source, Settings(llm_provider=provider, llm_model=None))["model"] == model
