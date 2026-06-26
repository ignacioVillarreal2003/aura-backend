from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.domain.field_limits import MAX_CONTENT_CHARS


class GeneralChatSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GENERAL_CHAT_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    max_response_chars: int = Field(default=MAX_CONTENT_CHARS, ge=1_000, le=MAX_CONTENT_CHARS)
