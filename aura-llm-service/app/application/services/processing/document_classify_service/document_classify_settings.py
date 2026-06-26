from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DocumentClassifyServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DOCUMENT_CLASSIFY_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    max_content_chars: int = Field(default=60_000, ge=1_000, le=500_000)
