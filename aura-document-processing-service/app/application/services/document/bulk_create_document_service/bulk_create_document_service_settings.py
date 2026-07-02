import logging
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.domain.field_limits import MAX_BULK_CREATE_DOCUMENTS

logger = logging.getLogger(__name__)


class BulkCreateDocumentServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BULK_CREATE_DOCUMENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    max_documents: int = Field(default=MAX_BULK_CREATE_DOCUMENTS, ge=1, le=MAX_BULK_CREATE_DOCUMENTS)
    max_total_size_mb: int = Field(default=200, ge=1, le=5000)

    @property
    def max_total_size_bytes(self) -> int:
        return self.max_total_size_mb * 1024 * 1024
