from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DocumentCollectionCatalogSettings(BaseSettings):
    """Outbound HTTP integration with aura-document-collection-service."""

    model_config = SettingsConfigDict(
        env_prefix="DOCUMENT_COLLECTION_SERVICE_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    base_url: Optional[str] = Field(
        default=None,
        description="Base URL of the collection service (e.g. https://collection:8000).",
    )
    request_timeout_seconds: float = Field(default=15.0, gt=0, le=120.0)
    page_size: int = Field(default=100, ge=1, le=100)
    max_pages: int = Field(default=500, ge=1, le=10000)
    fallback_bearer_token: Optional[str] = Field(
        default=None,
        description="Optional service token used when no Authorization header is present on the request.",
    )

    def normalized_base_url(self) -> Optional[str]:
        if self.base_url is None:
            return None
        u = str(self.base_url).strip().rstrip("/")
        return u if u else None
