from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AttachedDocumentsSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ATTACHED_DOCUMENTS_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    max_fragments: int = Field(default=60, ge=1, le=200)
    max_chars: Optional[int] = Field(default=None, ge=500, le=2_000_000)
    fair_distribution: bool = Field(default=True)
