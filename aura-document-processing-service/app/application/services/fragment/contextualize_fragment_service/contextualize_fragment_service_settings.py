from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ContextualizeFragmentServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CONTEXTUALIZE_FRAGMENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    concurrency: int = Field(default=4, ge=1, le=32)

    max_document_summary_chars: int = Field(default=2_000, ge=100, le=50_000)
