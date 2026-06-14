from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class GeneralChatSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GENERAL_CHAT_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    max_response_chars: int = Field(default=10_000, ge=1_000, le=200_000)
