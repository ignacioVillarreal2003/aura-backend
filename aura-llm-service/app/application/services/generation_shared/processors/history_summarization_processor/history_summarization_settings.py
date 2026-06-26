from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class HistorySummarizationSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HISTORY_SUMMARIZATION_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    summarize_over_chars: int = Field(default=6_000, ge=1_000, le=400_000)
    max_summary_chars: int = Field(default=1_500, ge=300, le=20_000)
    temperature: Optional[float] = Field(default=0.0, ge=0.0, le=2.0)
