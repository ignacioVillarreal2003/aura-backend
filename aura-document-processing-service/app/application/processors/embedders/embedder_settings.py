import logging
import re
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.application.processors.embedders.constants.embedder_type import EmbedderType

logger = logging.getLogger(__name__)

_DEVICE_PATTERN = re.compile(r"^(cpu|cuda)$")


class EmbedderSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="EMBEDDER_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    active_type: EmbedderType = Field(default=EmbedderType.ollama)
    max_batch_size: int = Field(default=64, ge=1, le=512)
    max_text_length: int = Field(default=8000, ge=1, le=100_000)
    max_retries: int = Field(default=3, ge=0, le=10)
    retry_delay: float = Field(default=1.0, gt=0, le=10.0)
    retry_max_delay: float = Field(default=10.0, gt=0, le=60.0)
    circuit_breaker_threshold: int = Field(default=5, ge=1, le=20)
    circuit_breaker_timeout: int = Field(default=60, ge=10, le=600)

    ollama_model: str = Field(default="nomic-embed-text:v1.5")
    ollama_url: str = Field(default="http://localhost:11434")
    ollama_request_timeout: int = Field(default=60, ge=5, le=300)

    huggingface_model: str = Field(default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    huggingface_device: str = Field(default="cpu")
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

        if not self.ollama_url.startswith(("http://", "https://")):
            raise ValueError("ollama_url must start with http:// or https://")

        self.ollama_url = self.ollama_url.rstrip("/")

        if self.retry_max_delay < self.retry_delay:
            raise ValueError(
                f"retry_max_delay ({self.retry_max_delay}) "
                f"must be >= retry_delay ({self.retry_delay})"
            )

    def _validate_huggingface(self) -> None:
        if not self.huggingface_model or not self.huggingface_model.strip():
            raise ValueError("huggingface_model cannot be empty")

        device = self.huggingface_device.lower()

        if not _DEVICE_PATTERN.match(device):
            raise ValueError(
                f"huggingface_device must be 'cpu' or 'cuda', "
                f"got '{self.huggingface_device}'"
            )

        if self.retry_max_delay < self.retry_delay:
            raise ValueError(
                f"retry_max_delay ({self.retry_max_delay}) "
                f"must be >= retry_delay ({self.retry_delay})"
            )

        self.huggingface_device = device
        self.huggingface_model = self.huggingface_model.strip()
