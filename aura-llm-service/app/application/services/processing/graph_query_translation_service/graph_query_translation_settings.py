from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class GraphQueryTranslationServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GRAPH_QUERY_TRANSLATION_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    max_question_chars: int = Field(default=4_000, ge=64, le=64_000)
    max_repair_attempts: int = Field(default=2, ge=0, le=3)
