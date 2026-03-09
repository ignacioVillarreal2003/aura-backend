import logging
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class EmbedderSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="EMBEDDER_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    ollama_model: str = Field(
        default="nomic-embed-text:v1.5"
    )
    ollama_base_url: str = Field(
        default="http://localhost:11434"
    )
    ollama_request_timeout: int = Field(
        default=60,
        ge=5,
        le=300
    )
    ollama_max_batch_size: int = Field(
        default=100,
        ge=1,
        le=500
    )
    ollama_max_text_length: int = Field(
        default=8000,
        ge=1,
        le=100000
    )
    ollama_max_retries: int = Field(
        default=3,
        ge=0,
        le=10
    )
    ollama_retry_delay: float = Field(
        default=1.0,
        gt=0,
        le=10.0
    )
    ollama_retry_max_delay: float = Field(
        default=10.0,
        gt=0,
        le=60.0
    )
    ollama_circuit_breaker_threshold: int = Field(
        default=5,
        ge=1,
        le=20
    )
    ollama_circuit_breaker_timeout: int = Field(
        default=60,
        ge=10,
        le=600
    )

    @field_validator(
        "ollama_base_url",
        mode="before"
    )
    @classmethod
    def validate_base_url(
            cls,
            v: str
    ) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("ollama_base_url must start with http:// or https://")
        return v.rstrip("/")

    @field_validator(
        "ollama_model",
        mode="before"
    )
    @classmethod
    def validate_model(
            cls,
            v: str
    ) -> str:
        if not v or not v.strip():
            raise ValueError("ollama_model cannot be empty")
        return v.strip()

    @model_validator(
        mode="after"
    )
    def validate_retry_coherence(
            self
    ) -> "EmbedderSettings":
        if self.ollama_retry_max_delay < self.ollama_retry_delay:
            raise ValueError(
                f"ollama_retry_max_delay ({self.ollama_retry_max_delay}) "
                f"must be >= ollama_retry_delay ({self.ollama_retry_delay})"
            )
        return self
