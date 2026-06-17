import logging
from functools import lru_cache
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class EnvironmentVariables(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    app_name: str = Field(default="aura llm service")
    app_version: str = Field(default="1.0.0")
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8000, ge=1, le=65535)
    app_reload: bool = Field(default=False)
    log_level: str = Field(default="INFO")

    cors_origins: list[str]
    environment: str = Field(default="development")

    max_request_body_bytes: int = Field(default=10 * 1024 * 1024, ge=1024)
    rate_limit_window_seconds: int = Field(default=60, ge=1, le=3600)
    rate_limit_default_per_window: int = Field(default=60, ge=1)
    rate_limit_strict_per_window: int = Field(default=20, ge=1)

    @field_validator(
        "log_level"
    )
    @classmethod
    def validate_log_level(
            cls,
            v: str
    ) -> str:
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()

        if v_upper not in valid_levels:
            raise ValueError(f"Invalid log_level: {v}. Must be one of {valid_levels}")

        return v_upper

    @field_validator(
        "cors_origins"
    )
    @classmethod
    def validate_cors_origins(
            cls,
            v: list[str]
    ) -> list[str]:
        if not v:
            raise ValueError("At least one CORS origin must be specified")

        return v

    def log_configuration(
            self
    ) -> None:
        logger.info("=" * 60)
        logger.info(f"App Name: {self.app_name}")
        logger.info(f"App Version: {self.app_version}")
        logger.info(f"Host: {self.app_host}:{self.app_port}")
        logger.info(f"Log Level: {self.log_level}")
        logger.info(f"Reload: {self.app_reload}")
        logger.info("=" * 60)

    def is_production(
            self
    ) -> bool:
        return self.environment.strip().lower() in {"production", "prod"}

    def is_development(
            self
    ) -> bool:
        return not self.is_production()


@lru_cache
def get_settings() -> EnvironmentVariables:
    return EnvironmentVariables()
