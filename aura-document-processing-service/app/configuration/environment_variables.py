import logging
from pathlib import Path
from typing import List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.domain.constants.embedder_type import EmbedderType
from app.domain.constants.text_cleaner_type import TextCleanerType
from app.domain.constants.text_splitter_type import TextSplitterType

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[2]


class EnvironmentVariables(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
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

    db_host: str = Field(
        ...,
        description="Database host"
    )
    db_port: int = Field(
        ...,
        ge=1,
        le=65535,
        description="Database port"
    )
    db_name: str = Field(
        ...,
        description="Database name"
    )
    db_user: str = Field(
        ...,
        description="Database user"
    )
    db_password: str = Field(
        ...,
        description="Database password"
    )
    db_driver: str = Field(
        default="postgresql+psycopg2",
        description="SQLAlchemy database driver"
    )

    minio_endpoint: str = Field(
        ...,
        description="MinIO endpoint URL"
    )
    minio_access_key: str = Field(
        ...,
        description="MinIO access key"
    )
    minio_secret_key: str = Field(
        ...,
        description="MinIO secret key"
    )
    minio_secure: bool = Field(
        default=False,
        description="Use HTTPS for MinIO connection"
    )

    text_cleaner_type: TextCleanerType = Field(
        default="basic",
        description="Cleaner strategy (basic, advanced, etc.)"
    )
    text_splitter_type: TextSplitterType = Field(
        default="recursive",
        description="Splitter strategy (character, sentence, recursive)"
    )
    embedder_type: EmbedderType = Field(
        default="huggingface",
        description="Embedder backend"
    )

    vector_dimension: int = Field(
        default=384,
        gt=0,
        description="Embedding vector dimension"
    )

    split_size: int = Field(
        default=600,
        gt=0,
        description="Text split chunk size"
    )

    split_overlap: int = Field(
        default=60,
        ge=0,
        description="Text split overlap"
    )

    max_file_size_mb: int = Field(
        default=20,
        ge=1,
        le=500,
        description="Maximum allowed file size in MB"
    )

    environment: str = Field(
        default="development",
        description="Application environment (development | production)"
    )

    @field_validator("split_overlap")
    @classmethod
    def validate_overlap(
            cls,
            v: int,
            info
    ) -> int:
        split_size = info.data.get("split_size")
        if split_size is not None and v >= split_size:
            raise ValueError("split_overlap debe ser menor que split_size")
        return v

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
