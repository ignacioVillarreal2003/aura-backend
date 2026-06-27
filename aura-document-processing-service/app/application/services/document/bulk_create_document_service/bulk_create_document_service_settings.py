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
