import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.config import Settings
from app.errors import AppError

TARGET_LANGUAGE_RE = re.compile(
    r"^[a-zA-Z]{2,3}(?:-[a-zA-Z]{4})?(?:-[a-zA-Z]{2}|\d{3})?$"
)


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: Literal["youtube", "manual"]
    youtubeUrl: Any = None
    text: Any = None
    title: Any = None
    targetLanguage: Any = None
    provider: Any = None
    model: Any = None
    temperature: Any = None
    maxOutputTokens: Any = None

    @model_validator(mode="before")
    @classmethod
    def require_object(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            raise AppError(400, "INVALID_REQUEST", "Request body must be a JSON object")
        return value


class AnalyzeSource(BaseModel):
    type: Literal["youtube", "manual"]
    youtube_url: str | None = None
    text: str | None = None
    title: str | None = None
    target_language: str
    provider: Any = None
    model: Any = None
    temperature: Any = None
    max_output_tokens: Any = None


class KeywordSource(BaseModel):
    type: Literal["youtube", "manual"]
    ref: str


class ExternalKeywordSource(BaseModel):
    citationId: str = Field(min_length=1, max_length=32)
    title: str = Field(min_length=1, max_length=300)
    url: str = Field(min_length=1, max_length=2048)


class AnalyzeKeyword(BaseModel):
    term: str
    candidateClippingId: str
    brief: str
    level1: str
    level2: str
    level3: str
    source: KeywordSource
    sources: list[KeywordSource] = Field(min_length=1)
    level2CitationIds: list[str] = Field(default_factory=list)
    level3CitationIds: list[str] = Field(default_factory=list)
    externalSources: list[ExternalKeywordSource] = Field(default_factory=list)


class AnalyzeCategory(BaseModel):
    categoryId: str
    title: str
    keywords: list[AnalyzeKeyword] = Field(min_length=1)


class AnalyzeResult(BaseModel):
    transcriptId: str
    sourceType: Literal["youtube", "manual"]
    categories: list[AnalyzeCategory]
    expiresInSeconds: int
    llm: dict[str, Any]
    videoId: str | None = None


def parse_analyze_request(payload: Any, settings: Settings) -> AnalyzeSource:
    if not isinstance(payload, dict):
        raise AppError(400, "INVALID_REQUEST", "Request body must be a JSON object")
    source_type = payload.get("type")
    if source_type not in {"youtube", "manual"}:
        raise AppError(400, "INVALID_TYPE", "type must be either 'youtube' or 'manual'")

    common = {"type", "title", "targetLanguage"}
    override_keys = {"provider", "model", "temperature", "maxOutputTokens"}
    allowed = common | ({"youtubeUrl"} if source_type == "youtube" else {"text"})
    if settings.allow_analyze_llm_overrides:
        allowed |= override_keys
    unknown = next((key for key in payload if key not in allowed), None)
    if unknown:
        raise AppError(400, "INVALID_REQUEST", f"Unsupported request field: {unknown}")

    title = _optional_nonempty(payload.get("title"), "INVALID_TITLE", "title")
    target_language = normalize_target_language(payload.get("targetLanguage"))
    values: dict[str, Any] = {
        "type": source_type,
        "title": title,
        "target_language": target_language,
    }
    if source_type == "youtube":
        values["youtube_url"] = _required_nonempty(
            payload.get("youtubeUrl"),
            "INVALID_YOUTUBE_URL",
            "youtubeUrl must be a non-empty string",
        )
    else:
        values["text"] = _required_nonempty(
            payload.get("text"), "INVALID_TEXT", "text must be a non-empty string"
        )

    if settings.allow_analyze_llm_overrides:
        values.update(
            provider=payload.get("provider"),
            model=payload.get("model"),
            temperature=payload.get("temperature"),
            max_output_tokens=payload.get("maxOutputTokens"),
        )
    try:
        return AnalyzeSource.model_validate(values)
    except Exception as error:
        raise AppError(400, "INVALID_REQUEST", "Invalid LLM override values") from error


def normalize_target_language(value: Any) -> str:
    if value is None:
        return "en"
    if not isinstance(value, str) or not value.strip() or not TARGET_LANGUAGE_RE.match(value.strip()):
        raise AppError(
            400,
            "INVALID_TARGET_LANGUAGE",
            "targetLanguage must be a valid BCP-47 language code",
        )
    parts = value.strip().split("-")
    normalized = [parts[0].lower()]
    for part in parts[1:]:
        normalized.append(part.title() if len(part) == 4 else part.upper() if len(part) == 2 else part)
    return "-".join(normalized)


def assert_transcript_text(value: Any) -> str:
    if not isinstance(value, str):
        raise AppError(502, "INVALID_TRANSCRIPT", "Transcript text is invalid")
    text = value.strip()
    if not text:
        raise AppError(502, "EMPTY_TRANSCRIPT", "Transcript is empty or unavailable")
    if len(text) < 80:
        raise AppError(502, "SHORT_TRANSCRIPT", "Transcript is too short for analysis")
    return text


def _required_nonempty(value: Any, code: str, message: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AppError(400, code, message)
    return value.strip()


def _optional_nonempty(value: Any, code: str, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise AppError(400, code, f"{field} must be a non-empty string when provided")
    return value.strip()
