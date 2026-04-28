from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RetrieveFragmentsSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RETRIEVE_FRAGMENTS_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    large_document_threshold: int = Field(default=5, ge=2, le=50)
