import pytest

from app.config import Settings
from app.errors import AppError
from app.llm import resolve_llm_options
from app.schemas import normalize_target_language, parse_analyze_request


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
