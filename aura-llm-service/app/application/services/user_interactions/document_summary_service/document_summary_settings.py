from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DocumentSummarySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DOCUMENT_SUMMARY_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    max_title_chars: int = Field(default=100, ge=1, le=1_000)
    max_description_chars: int = Field(default=1_000, ge=100, le=20_000)
    max_summary_chars: int = Field(default=10_000, ge=100, le=100_000)
