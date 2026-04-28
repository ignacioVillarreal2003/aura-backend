from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DocumentQuestionServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DOCUMENT_QUESTION_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    pipeline_plugins: list[str] = Field(
        default_factory=lambda: [
            "rewrite_query",
            "retrieve_context",
            "generate_answer",
            "fallback_answer",
        ]
    )

    rewrite_query_enabled: bool = Field(default=True)
    rewrite_query_history_window: int = Field(default=4, ge=1, le=20)

    generate_answer_history_window: int = Field(default=5, ge=0, le=20)

    use_keywords: bool = Field(default=True)
    question_max_fragments: int = Field(default=8, ge=1, le=50)
    keywords_max_fragments: int = Field(default=5, ge=1, le=50)
    use_rerank: bool = Field(default=True)
    rerank_max_fragments: Optional[int] = Field(default=5, ge=1, le=50)

    @model_validator(mode="after")
    def validate_retrieval_coherence(self) -> "DocumentQuestionServiceSettings":
        if self.keywords_max_fragments > self.question_max_fragments:
            raise ValueError("keywords_max_fragments must not exceed question_max_fragments.")
        if self.rerank_max_fragments is not None and not self.use_rerank:
            raise ValueError("rerank_max_fragments requires use_rerank to be true.")
        if self.rerank_max_fragments is not None and self.rerank_max_fragments > self.question_max_fragments:
            raise ValueError("rerank_max_fragments must not exceed question_max_fragments.")
        if self.rerank_max_fragments is not None and self.rerank_max_fragments < 1:
            raise ValueError("rerank_max_fragments must be at least one when set.")
        return self
