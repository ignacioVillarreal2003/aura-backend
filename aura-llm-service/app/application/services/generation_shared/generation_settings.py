from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class GenerationSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GENERATION_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    history_messages_window: int = Field(default=4, ge=0, le=20)
    max_context_chars: int = Field(default=10_000, ge=1_000, le=50_000)
    attached_reserve_ratio: float = Field(default=0.6, ge=0.0, le=1.0)
