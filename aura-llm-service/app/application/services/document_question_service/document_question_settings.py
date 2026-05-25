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

    question_processor_enabled: bool = Field(default=True)
    history_messages_window: int = Field(default=4, ge=1, le=20)
    use_keywords: bool = Field(default=True)

    semantic_fragments_per_lane: int = Field(default=5, ge=1, le=50)
    bm25_fragments_per_lane: int = Field(default=2, ge=1, le=50)
    enable_dual_bm25: bool = Field(default=True)

    use_rerank: bool = Field(default=True)
    rerank_max_fragments: Optional[int] = Field(default=8, ge=1, le=100)
    adjacent_chunks: int = Field(default=1, ge=0, le=3)

    # Maximum characters for the context string passed to the LLM.
    # Prevents context overflow when many/large fragments are retrieved.
    max_context_chars: int = Field(default=12_000, ge=1_000, le=50_000)

    @model_validator(mode="after")
    def validate_coherence(self) -> "DocumentQuestionServiceSettings":
        if not self.use_rerank:
            self.rerank_max_fragments = None
        return self
