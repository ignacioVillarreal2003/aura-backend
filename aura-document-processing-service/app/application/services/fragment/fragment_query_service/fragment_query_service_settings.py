from typing import ClassVar, Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class FragmentQueryServiceSettings(BaseSettings):
    REQUIRED_PERMISSIONS: ClassVar[frozenset[str]] = frozenset({"DOCUMENT_GET"})

    model_config = SettingsConfigDict(
        env_prefix="FRAGMENT_QUERY_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    max_fragments: int = Field(default=50, ge=1, le=100)
    max_document_ids: int = Field(default=50, ge=1, le=100)
    min_question_length: int = Field(default=1, ge=1)
    max_question_length: int = Field(default=16_000, ge=1, le=100_000)
    similarity_threshold: float = Field(default=0.3, ge=0.0, le=1.0)

    rerank_enabled: bool = Field(default=False)
    rerank_model_name: str = Field(default="BAAI/bge-reranker-v2-m3")
    rerank_device: Optional[str] = Field(default=None)
    rerank_min_fragments: int = Field(default=6, ge=1, le=50)
    rerank_default_top_n: int = Field(default=6, ge=1, le=50)
    rerank_min_score: float = Field(default=-10.0)
    rerank_batch_size: int = Field(default=16, ge=1, le=512)

    @field_validator("rerank_device", mode="before")
    @classmethod
    def normalize_rerank_device(cls, value: Optional[str]) -> Optional[str]:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        return value.strip().lower()

    @model_validator(mode="after")
    def validate_coherence(self) -> "FragmentQueryServiceSettings":
        if self.min_question_length >= self.max_question_length:
            raise ValueError("The minimum question length must be strictly less than the maximum question length.")
        if self.rerank_default_top_n > self.max_fragments:
            raise ValueError("rerank_default_top_n must not exceed max_fragments.")
        return self
