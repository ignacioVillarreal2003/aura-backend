from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.application.services.generation_shared.token_estimation import (
    DEFAULT_MAX_CONTEXT_CHARS,
    chars_to_tokens,
    tokens_to_chars,
)


class GenerationSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GENERATION_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    history_messages_window: int = Field(default=4, ge=0, le=20)
    max_history_chars: int = Field(default=3_000, ge=0, le=200_000)
    max_context_chars: int = Field(default=DEFAULT_MAX_CONTEXT_CHARS, ge=1_000, le=50_000)
    max_context_tokens: int = Field(default=chars_to_tokens(DEFAULT_MAX_CONTEXT_CHARS), ge=256, le=32_768)
    attached_reserve_ratio: float = Field(default=0.6, ge=0.0, le=1.0)

    def effective_max_context_chars(self) -> int:
        return min(self.max_context_chars, tokens_to_chars(self.max_context_tokens))
