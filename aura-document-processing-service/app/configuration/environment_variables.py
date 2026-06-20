import logging
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

_PRODUCTION_ENVIRONMENT_NAMES = frozenset({"production", "prod"})

_DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000", "http://127.0.0.1:3000",
    "http://localhost:4200", "http://127.0.0.1:4200",
    "http://localhost:8000", "http://127.0.0.1:8000",
    "http://localhost:8001", "http://127.0.0.1:8001",
    "http://localhost:8002", "http://127.0.0.1:8002",
    "http://localhost:8003", "http://127.0.0.1:8003",
    "http://localhost:8004", "http://127.0.0.1:8004",
    "http://localhost:8005", "http://127.0.0.1:8005",
]


class EnvironmentVariables(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    app_name: str = Field(default="aura document processing service")
    app_version: str = Field(default="1.0.0")
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8000, ge=1, le=65535)
    app_reload: bool = Field(default=False)
    require_gpu: bool = Field(default=False)
    log_level: str = Field(default="INFO")
    cors_origins: list[str] = Field(default_factory=lambda: list(_DEFAULT_CORS_ORIGINS))
    environment: str = Field(default="development")

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

    @model_validator(mode="after")
    def validate_cors_not_wildcard_in_production(self) -> "EnvironmentVariables":
        if self.is_production() and any(
                (o or "").strip() == "*" for o in self.cors_origins
        ):
            raise ValueError(
                "Wildcard CORS origin '*' is not allowed when "
                f"ENVIRONMENT='{self.environment}'. Specify explicit origins."
            )

        return self

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

    def is_development(
            self
    ) -> bool:
        return not self.is_production()

    def is_production(
            self
    ) -> bool:
        return self.environment.strip().lower() in _PRODUCTION_ENVIRONMENT_NAMES


environment_variables = EnvironmentVariables()

if environment_variables.is_development():
    environment_variables.log_configuration()
