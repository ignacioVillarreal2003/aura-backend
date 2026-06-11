from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DocumentSearchServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DOCUMENT_SEARCH_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    similarity_threshold: float = Field(default=0.3, ge=0.0, le=1.0)
    candidate_pool_size: int = Field(default=200, ge=1, le=2_000)
