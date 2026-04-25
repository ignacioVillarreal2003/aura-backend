from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DocumentQueryServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DOCUMENT_QUERY_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    default_page: int = Field(default=1, ge=1, le=1_000_000)
    default_page_size: int = Field(default=20, ge=1, le=1000)
    max_page_size: int = Field(default=100, ge=1, le=1000)
    max_filter_length: int = Field(default=255, ge=1, le=4000)

