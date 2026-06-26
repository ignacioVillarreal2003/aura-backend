import logging
from typing import Literal, Optional
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

    active_type: EmbedderType = Field(default=EmbedderType.huggingface)

    vector_dimension: Optional[int] = Field(default=1024, gt=0)

    max_batch_size: int = Field(default=128, ge=1, le=512)
    max_text_length: int = Field(default=8000, ge=1, le=100_000)
    max_batch_tokens: int = Field(default=131_072, ge=0, le=4_000_000)

    max_retries: int = Field(default=3, ge=0, le=10)
    retry_delay: float = Field(default=1.0, gt=0, le=10.0)
    retry_max_delay: float = Field(default=10.0, gt=0, le=60.0)
    circuit_breaker_threshold: int = Field(default=5, ge=1, le=20)
    circuit_breaker_timeout: int = Field(default=60, ge=10, le=600)

    ollama_model: str = Field(default="qwen3-embedding:0.6b")
    ollama_url: str = Field(default="http://localhost:11434")
    ollama_request_timeout: int = Field(default=60, ge=5, le=300)

    huggingface_model: str = Field(default="BAAI/bge-m3")
    huggingface_token: Optional[str] = Field(default=None)
    huggingface_device: Literal["cpu", "cuda"] = Field(default="cuda")
    huggingface_normalize_embeddings: bool = Field(default=True)
    huggingface_max_seq_length: Optional[int] = Field(default=8192, gt=0, le=8192)

    huggingface_torch_dtype: Literal["auto", "float32", "float16", "bfloat16"] = Field(default="auto")
    huggingface_query_instruction: str = Field(default="")
    huggingface_embed_instruction: str = Field(default="")

    @property
    def active_model_name(self) -> str:
        if self.active_type == EmbedderType.ollama:
            return self.ollama_model
        if self.active_type == EmbedderType.huggingface:
            return self.huggingface_model
        return str(self.active_type)

    @property
    def active_embedding_identity(self) -> str:
        parts = [
            f"type={self.active_type.value}",
            f"model={self.active_model_name}",
            f"dim={self.vector_dimension}",
        ]
        if self.active_type == EmbedderType.huggingface:
            parts.append(f"norm={int(self.huggingface_normalize_embeddings)}")
            if self.huggingface_max_seq_length is not None:
                parts.append(f"msl={self.huggingface_max_seq_length}")
            parts.append(f"qi={self.huggingface_query_instruction}")
            parts.append(f"di={self.huggingface_embed_instruction}")
        return "v1|" + "|".join(parts)

    @model_validator(mode="after")
    def validate_active_embedder_settings(self) -> "EmbedderSettings":
        self._validate_all()

        if self.active_type == EmbedderType.ollama:
            self._validate_ollama()
        elif self.active_type == EmbedderType.huggingface:
            self._validate_huggingface()

        if self.vector_dimension is None:
            raise ValueError("EMBEDDER_VECTOR_DIMENSION must be set and match the active embedding model.")

        return self

    def _validate_all(self) -> None:
        if self.retry_max_delay < self.retry_delay:
            raise ValueError("The maximum retry delay must be greater than or equal to the initial retry delay.")
        if self.max_batch_size > 1 and self.max_text_length < 32:
            raise ValueError("max_text_length is too low for batched embeddings.")

    def _validate_ollama(self) -> None:
        if (not self.ollama_model or
                not self.ollama_model.strip()):
            raise ValueError("The Ollama model name cannot be empty when Ollama is the active embedder.")

        self.ollama_model = self.ollama_model.strip()

        if not self.ollama_url.startswith(("http://", "https://")):
            raise ValueError("The Ollama URL must start with http:// or https://.")

        self.ollama_url = self.ollama_url.rstrip("/")
        if not self.ollama_url:
            raise ValueError("The Ollama URL cannot be empty.")

    def _validate_huggingface(self) -> None:
        if (not self.huggingface_model
                or not self.huggingface_model.strip()):
            raise ValueError("The Hugging Face model name cannot be empty when Hugging Face is the active embedder.")

        self.huggingface_model = self.huggingface_model.strip()
