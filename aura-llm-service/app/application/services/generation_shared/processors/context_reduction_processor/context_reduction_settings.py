from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.application.services.generation_shared.token_estimation import DEFAULT_MAX_CONTEXT_CHARS


class ContextReductionSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CONTEXT_REDUCTION_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    max_batch_chars: int = Field(default=8_000, ge=1_000, le=20_000)
    max_batch_tokens: int = Field(default=2_000, ge=256, le=32_768)
    max_passes: int = Field(default=3, ge=1, le=5)
    max_context_chars: int = Field(default=DEFAULT_MAX_CONTEXT_CHARS, ge=1_000, le=50_000)
    max_concurrent_batches: int = Field(default=4, ge=1, le=32)
    deadline_seconds: float = Field(default=60.0, gt=0, le=600.0)
    temperature: Optional[float] = Field(default=0.0, ge=0.0, le=2.0)
