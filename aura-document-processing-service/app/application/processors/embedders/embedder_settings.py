import logging
from typing import Literal, Optional
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.application.processors.embedders.constants.embedder_type import EmbedderType

logger = logging.getLogger(__name__)

_OLLAMA_MODEL_DIMENSIONS: dict[str, int] = {
    "nomic-embed-text:v1.5": 768,
    "nomic-embed-text-v2-moe": 768,
    "qwen3-embedding:0.6b": 1024,
    "qwen3-embedding:4b": 2560,
    "embeddinggemma:300m": 768,
    "mxbai-embed-large:335m": 1024
}

_HUGGINGFACE_MODEL_DIMENSIONS: dict[str, int] = {
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2": 384,
    "sentence-transformers/paraphrase-multilingual-mpnet-base-v2": 768,
    "intfloat/multilingual-e5-large": 1024,
    "sentence-transformers/distiluse-base-multilingual-cased-v2": 512
}


class EmbedderSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="EMBEDDER_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    active_type: EmbedderType = Field(default=EmbedderType.ollama)
    vector_dimension: Optional[int] = Field(default=None, gt=0)

    max_batch_size: int = Field(default=64, ge=1, le=512)
    max_text_length: int = Field(default=8000, ge=1, le=100_000)
    max_retries: int = Field(default=3, ge=0, le=10)
    retry_delay: float = Field(default=1.0, gt=0, le=10.0)
    retry_max_delay: float = Field(default=10.0, gt=0, le=60.0)
    circuit_breaker_threshold: int = Field(default=5, ge=1, le=20)
    circuit_breaker_timeout: int = Field(default=60, ge=10, le=600)

    ollama_model: Literal[
                      "nomic-embed-text:v1.5",
                      "nomic-embed-text-v2-moe",
                      "qwen3-embedding:0.6b",
                      "qwen3-embedding:4b",
                      "embeddinggemma:300m",
                      "mxbai-embed-large:335m"
                  ] | str = Field(default="nomic-embed-text:v1.5")
    ollama_url: str = Field(default="http://localhost:11434")
    ollama_request_timeout: int = Field(default=60, ge=5, le=300)

    huggingface_model: Literal[
                           "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                           "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
                           "intfloat/multilingual-e5-large",
                           "sentence-transformers/distiluse-base-multilingual-cased-v2"
                       ] | str = Field(default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    huggingface_device: Literal["cpu", "cuda"] = "cpu"
    huggingface_normalize_embeddings: bool = Field(default=True)

    @model_validator(
        mode="after"
    )
    def validate_active_embedder_settings(
            self
    ) -> "EmbedderSettings":
        self._validate_all()

        if self.active_type == EmbedderType.ollama:
            self._validate_ollama()
            if self.vector_dimension is None:
                self.vector_dimension = _OLLAMA_MODEL_DIMENSIONS.get(self.ollama_model)

        elif self.active_type == EmbedderType.huggingface:
            self._validate_huggingface()
            if self.vector_dimension is None:
                self.vector_dimension = _HUGGINGFACE_MODEL_DIMENSIONS.get(self.huggingface_model)

        if self.vector_dimension is None:
            raise ValueError(
                "Could not resolve vector dimension for model. "
                "Add it to the dimensions dictionary or set vector dimension explicitly."
            )

        return self

    def _validate_all(
            self
    ):
        if self.retry_max_delay < self.retry_delay:
            raise ValueError("The maximum retry delay must be greater than or equal to the initial retry delay.")

    def _validate_ollama(
            self
    ) -> None:
        if (not self.ollama_model or
                not self.ollama_model.strip()):
            raise ValueError("The Ollama model name cannot be empty.")

        self.ollama_model = self.ollama_model.strip()

        if not self.ollama_url.startswith(("http://", "https://")):
            raise ValueError("The Ollama URL must start with http:// or https://.")

        self.ollama_url = self.ollama_url.rstrip("/")

    def _validate_huggingface(
            self
    ) -> None:
        if (not self.huggingface_model
                or not self.huggingface_model.strip()):
            raise ValueError("The Hugging Face model name cannot be empty.")

        self.huggingface_model = self.huggingface_model.strip()
