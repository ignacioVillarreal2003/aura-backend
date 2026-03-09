import logging
from pathlib import Path
from typing import List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[2]


class EnvironmentVariables(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    app_name: str = Field(
        default="Aura document processing service",
        description="Application name"
    )
    app_version: str = Field(
        default="1.0.0",
        description="Application version"
    )
    app_host: str = Field(
        default="0.0.0.0",
        description="Host to bind the application"
    )
    app_port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="Port to bind the application"
    )
    app_reload: bool = Field(
        default=False,
        description="Enable auto-reload for development"
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )
    cors_origins: List[str] = Field(
        default=["*"],
        description="Allowed CORS origins"
    )

    environment: str = Field(
        default="development",
        description="Application environment (development | production)"
    )

    @field_validator("log_level")
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

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(
            cls,
            v: List[str]
    ) -> List[str]:
        if not v:
            raise ValueError("At least one CORS origin must be specified")

        return v

    def log_configuration(
            self
    ) -> None:
        logger.info("=" * 60)
        logger.info("Application Configuration")
        logger.info("=" * 60)
        logger.info(f"App Name: {self.app_name}")
        logger.info(f"App Version: {self.app_version}")
        logger.info(f"Host: {self.app_host}:{self.app_port}")
        logger.info(f"Log Level: {self.log_level}")
        logger.info(f"Reload: {self.app_reload}")
        logger.info("=" * 60)

    def is_development(
            self
    ) -> bool:
        return self.app_reload or self.log_level == "DEBUG"

    def is_production(
            self
    ) -> bool:
        return not self.is_development()


environment_variables = EnvironmentVariables()

if environment_variables.is_development():
    environment_variables.log_configuration()
