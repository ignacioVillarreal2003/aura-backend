import logging
from pathlib import Path
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

    def is_development(
            self
    ) -> bool:
        return self.environment.lower() == "development"

    def is_production(
            self
    ) -> bool:
        return not self.is_development()

    def log_configuration(
            self
    ) -> None:
        logger.info("=" * 60)
        logger.info("Environment configuration loaded")
        logger.info(f"Environment: {self.environment}")
        logger.info(f"DB Host: {self.db_host}:{self.db_port}")
        logger.info(f"Cleaner: {self.cleaner_type}")
        logger.info(f"Splitter: {self.splitter_type}")
        logger.info(f"Embedder: {self.embedder_type}")
        logger.info("=" * 60)


environment_variables = EnvironmentVariables()

if environment_variables.is_development():
    environment_variables.log_configuration()
