from typing import ClassVar
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PostProcessDocumentServiceSettings(BaseSettings):
    REQUIRED_PERMISSIONS: ClassVar[frozenset[str]] = frozenset({"DOCUMENT_UPDATE"})

    model_config = SettingsConfigDict(
        env_prefix="POST_PROCESS_DOCUMENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    max_document_ids: int = Field(default=500, ge=1, le=10000)
    llm_timeout_seconds: float = Field(default=30.0, gt=0, le=300.0)
    max_errors_in_status: int = Field(default=500, ge=10, le=10000)
