import logging
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.application.processors.embedders.constants.embedder_type import EmbedderType

logger = logging.getLogger(__name__)


class EmbedderSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="EMBEDDER_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    active_type: EmbedderType = Field(default=EmbedderType.ollama)

    ollama_model: str = Field(default="nomic-embed-text:v1.5")
    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_request_timeout: int = Field(default=60, ge=5, le=300)
    ollama_max_batch_size: int = Field(default=100, ge=1, le=500)
    ollama_max_text_length: int = Field(default=8000, ge=1, le=100000)
    ollama_max_retries: int = Field(default=3, ge=0, le=10)
    ollama_retry_delay: float = Field(default=1.0, gt=0, le=10.0)
    ollama_retry_max_delay: float = Field(default=10.0, gt=0, le=60.0)
    ollama_circuit_breaker_threshold: int = Field(default=5, ge=1, le=20)
    ollama_circuit_breaker_timeout: int = Field(default=60, ge=10, le=600)

    huggingface_model: str = Field(
        default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    huggingface_device: str = Field(
        default="cpu",
        description="Inference device: cpu, cuda, mps"
    )
    huggingface_max_batch_size: int = Field(default=64, ge=1, le=512)
    huggingface_max_text_length: int = Field(default=8000, ge=1, le=100000)
    huggingface_normalize_embeddings: bool = Field(default=True)

    @model_validator(mode="after")
    def validate_active_embedder_settings(self) -> "EmbedderSettings":
        if self.active_type == EmbedderType.ollama:
            self._validate_ollama()
        elif self.active_type == EmbedderType.huggingface:
            self._validate_huggingface()
        return self

    def _validate_ollama(self) -> None:
        if not self.ollama_model or not self.ollama_model.strip():
            raise ValueError("ollama_model cannot be empty")

        if not self.ollama_base_url.startswith(("http://", "https://")):
            raise ValueError("ollama_base_url must start with http:// or https://")

        self.ollama_base_url = self.ollama_base_url.rstrip("/")

        if self.ollama_retry_max_delay < self.ollama_retry_delay:
            raise ValueError(
                f"ollama_retry_max_delay ({self.ollama_retry_max_delay}) "
                f"must be >= ollama_retry_delay ({self.ollama_retry_delay})"
            )

    def _validate_huggingface(self) -> None:
        if not self.huggingface_model or not self.huggingface_model.strip():
            raise ValueError("huggingface_model cannot be empty")

        allowed_devices = {"cpu", "cuda", "mps"}
        if self.huggingface_device.lower() not in allowed_devices:
            raise ValueError(
                f"huggingface_device must be one of {allowed_devices}, "
                f"got '{self.huggingface_device}'"
            )

        self.huggingface_device = self.huggingface_device.lower()
        self.huggingface_model = self.huggingface_model.strip()
