from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    port: int = 3000
    database_url: str = "postgresql+psycopg://reforge:reforge@localhost:5432/reforge"
    redis_url: str = "redis://localhost:6379"
    llm_provider: str = "openai"
    llm_model: str | None = None
    llm_temperature: float = 0.2
    llm_max_output_tokens: int | None = 3000
    allow_analyze_llm_overrides: bool = False
    explanation_enrichment_enabled: bool = False
    explanation_enrichment_max_sources: int = Field(default=3, ge=1, le=3)
    explanation_enrichment_max_concurrency: int = Field(default=3, ge=1, le=8)
    openai_api_key: str = ""
    gemini_api_key: str = ""
    anthropic_api_key: str = ""

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+psycopg://", 1)
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value

    @field_validator("llm_provider")
    @classmethod
    def normalize_provider(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"openai", "gemini", "claude"}:
            raise ValueError("LLM_PROVIDER must be openai, gemini, or claude")
        return normalized


@lru_cache
def get_settings() -> Settings:
    return Settings()
