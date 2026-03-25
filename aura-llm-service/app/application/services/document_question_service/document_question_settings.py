import logging
from typing import Optional
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class DocumentQuestionServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DOCUMENT_QUESTION_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    max_context_fragments: int = Field(default=6, ge=1, le=10)

    min_question_length: int = Field(default=1, ge=1)
    max_question_length: int = Field(default=1000, ge=1, le=10_000)

    max_history_messages: int = Field(default=3, ge=0, le=20)

    query_rewrite_enabled: bool = Field(default=True)

    rerank_threshold: int = Field(default=3, ge=1, le=20)
    max_reranked_fragments: int = Field(default=3, ge=1, le=10)

    @model_validator(mode="after")
    def validate_coherence(self) -> "DocumentQuestionServiceSettings":
        if self.min_question_length > self.max_question_length:
            raise ValueError(
                f"min_question_length ({self.min_question_length}) must be "
                f"less than max_question_length ({self.max_question_length})"
            )
        if self.max_reranked_fragments > self.max_context_fragments:
            raise ValueError(
                f"max_reranked_fragments ({self.max_reranked_fragments}) cannot exceed "
                f"max_context_fragments ({self.max_context_fragments})"
            )
        return self
