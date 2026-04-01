from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RetrieveActionFragmentsSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RETRIEVE_ACTION_FRAGMENTS_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    large_document_threshold: int = Field(default=10, ge=2, le=100)
