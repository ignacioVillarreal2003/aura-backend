from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DocumentCollectionCatalogSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DOCUMENT_COLLECTION_SERVICE_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    accessible_collections_url: str = Field(...)
    request_timeout_seconds: float = Field(default=15.0, gt=0, le=120.0)
    page_size: int = Field(default=100, ge=1, le=100)
    max_pages: int = Field(default=500, ge=1, le=10000)
