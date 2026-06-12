import logging
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

DEFAULT_SERVICE_API_KEY = "service_api_key"
_PRODUCTION_ENVIRONMENT_NAMES = frozenset({"production", "prod"})


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
    log_level: str = Field(default="INFO")
    cors_origins: list[str] = Field(default=["*"])
    environment: str = Field(default="development")
    service_api_key: str = Field(default="service_api_key")

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
    def validate_service_api_key_strength(
            self
    ) -> "EnvironmentVariables":
        if self.service_api_key == DEFAULT_SERVICE_API_KEY:
            if self.is_production():
                raise ValueError(
                    "SERVICE_API_KEY is still the default value; "
                    "set a strong secret before running in production."
                )
            logger.warning(
                "SERVICE_API_KEY is using the default development value; "
                "set a strong secret before deploying."
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
