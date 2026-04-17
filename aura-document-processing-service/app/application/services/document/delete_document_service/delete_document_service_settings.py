from typing import ClassVar
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DeleteDocumentServiceSettings(BaseSettings):
    REQUIRED_PERMISSIONS: ClassVar[frozenset[str]] = frozenset({"DOCUMENT_DELETE", "FRAGMENT_DELETE"})

    model_config = SettingsConfigDict(
        env_prefix="DELETE_DOCUMENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    max_ids_per_operation: int = Field(default=10000, ge=1, le=100000)
