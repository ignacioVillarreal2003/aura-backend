from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DocumentActionSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DOCUMENT_ACTION_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    max_title_chars: int = Field(default=100, ge=1, le=1_000)
    max_description_chars: int = Field(default=1_000, ge=100, le=20_000)
    max_result_chars: int = Field(default=50_000, ge=100, le=200_000)
