from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RetrieveContextSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RETRIEVE_CONTEXT_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    max_fragments: int = Field(default=12, ge=1, le=50)
