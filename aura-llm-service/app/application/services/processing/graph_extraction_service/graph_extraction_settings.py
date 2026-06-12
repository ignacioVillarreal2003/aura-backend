from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_BASE_DIR = Path(__file__).resolve().parents[4]


class GraphExtractionServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GRAPH_EXTRACTION_",
        env_file=_BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    max_content_chars: int = Field(default=20_000, ge=1_000, le=200_000)
    max_repair_attempts: int = Field(default=1, ge=0, le=3)
    min_relation_confidence: float = Field(default=0.3, ge=0.0, le=1.0)
