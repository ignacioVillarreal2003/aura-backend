import logging
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class RateLimiterSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RATE_LIMIT_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    strict_rate: int = Field(default=20, ge=1, le=100_000)
    default_rate: int = Field(default=60, ge=1, le=100_000)
    window_seconds: int = Field(default=60, ge=1, le=86_400)
    fail_open: bool = Field(default=True)

    @model_validator(mode="after")
    def validate_tiers(self) -> "RateLimiterSettings":
        if self.strict_rate > self.default_rate:
            raise ValueError(
                f"strict_rate ({self.strict_rate}) must not exceed default_rate "
                f"({self.default_rate}); the strict tier is meant to be the tighter limit."
            )
        return self
