from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ContextReductionSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CONTEXT_REDUCTION_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    enable_context_reduction: bool = Field(default=True)
    reduction_batch_chars: int = Field(default=8_000, ge=1_000, le=20_000)
    max_reduction_passes: int = Field(default=3, ge=1, le=5)
    max_context_chars: int = Field(default=10_000, ge=1_000, le=50_000)
