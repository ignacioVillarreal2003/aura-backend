from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_BASE_DIR = Path(__file__).resolve().parents[4]


class GraphQueryTranslationServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GRAPH_QUERY_TRANSLATION_",
        env_file=_BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    max_question_chars: int = Field(default=4_000, ge=64, le=64_000)
