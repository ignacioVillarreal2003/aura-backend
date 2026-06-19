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
    "sentence-transformers/distiluse-base-multilingual-cased-v2": 512,
    "BAAI/bge-m3": 1024,
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
                           "sentence-transformers/distiluse-base-multilingual-cased-v2",
                           "BAAI/bge-m3",
                       ] | str = Field(default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    huggingface_token: Optional[str] = Field(default=None)
    huggingface_device: Literal["cpu", "cuda"] = "cpu"
    huggingface_normalize_embeddings: bool = Field(default=True)

    huggingface_query_instruction: str = Field(default="")
    huggingface_embed_instruction: str = Field(default="")

    @property
    def active_model_name(self) -> str:
        """The model name of the currently-active embedder.

        Persisted per fragment (see Fragment.embedding_model) so the row records
        exactly which model produced its vector — enabling audit and selective
        re-embedding when the embedding model changes.
        """
        if self.active_type == EmbedderType.ollama:
            return self.ollama_model
        if self.active_type == EmbedderType.huggingface:
            return self.huggingface_model
        return str(self.active_type)

    @property
    def active_embedding_identity(self) -> str:
        """Stable identity of the active embedding configuration.

        Cosine similarity is only meaningful between vectors produced by the *same*
        configuration. This identity is persisted per fragment (Fragment.embedding_identity)
        and matched at query time, so a partially re-embedded corpus never mixes
        incompatible vector spaces, and a re-embed treats a config change as stale.

        It captures every input that shifts the vector space: backend type, model,
        dimension, normalization and the query/document instruction prefixes — an
        instruction change silently moves the space, so it must invalidate old vectors.
        The ``v1`` prefix lets the format evolve without colliding with stored values.
        """
        parts = [
            f"type={self.active_type.value}",
            f"model={self.active_model_name}",
            f"dim={self.vector_dimension}",
        ]
        if self.active_type == EmbedderType.huggingface:
            parts.append(f"norm={int(self.huggingface_normalize_embeddings)}")
            parts.append(f"qi={self.huggingface_query_instruction}")
            parts.append(f"di={self.huggingface_embed_instruction}")
        return "v1|" + "|".join(parts)

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
    ) -> None:
        if self.retry_max_delay < self.retry_delay:
            raise ValueError("The maximum retry delay must be greater than or equal to the initial retry delay.")
        if self.max_batch_size > 1 and self.max_text_length < 32:
            raise ValueError("max_text_length is too low for batched embeddings.")

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
        if not self.ollama_url:
            raise ValueError("The Ollama URL cannot be empty.")

    def _validate_huggingface(
            self
    ) -> None:
        if (not self.huggingface_model
                or not self.huggingface_model.strip()):
            raise ValueError("The Hugging Face model name cannot be empty.")

        self.huggingface_model = self.huggingface_model.strip()

        # Auto-apply e5 asymmetric prefixes when not explicitly set
        if "e5" in self.huggingface_model.lower():
            if not self.huggingface_query_instruction:
                self.huggingface_query_instruction = "query: "
            if not self.huggingface_embed_instruction:
                self.huggingface_embed_instruction = "passage: "
