from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.application.services.generation_shared.generation_settings import GenerationSettings
from app.application.services.generation_shared.processors.attached_documents_processor.attached_documents_settings import (
    AttachedDocumentsSettings,
)
from app.application.services.generation_shared.processors.section_context_processor.section_context_settings import (
    SectionContextSettings,
)
from app.application.services.generation_shared.processors.context_reduction_processor.context_reduction_settings import (
    ContextReductionSettings,
)
from app.application.services.generation_shared.processors.context_retrieval_processor.context_retrieval_settings import (
    ContextRetrievalSettings,
)
from app.application.services.generation_shared.processors.query_reformulation_processor.query_reformulation_settings import (
    QueryReformulationSettings,
)
from app.application.services.generation_shared.token_estimation import chars_to_tokens
from app.domain.field_limits import MAX_CONTENT_CHARS


class DocumentQuestionServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DOCUMENT_QUESTION_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    history_messages_window: int = Field(default=4, ge=0, le=20)
    rewrite_query: bool = Field(default=True)
    use_keywords: bool = Field(default=True)

    semantic_fragments_per_lane: int = Field(default=5, ge=1, le=50)
    bm25_fragments_per_lane: int = Field(default=2, ge=1, le=50)
    use_rerank: bool = Field(default=True)
    rerank_max_fragments: int = Field(default=8, ge=1, le=100)
    adjacent_chunks: int = Field(default=1, ge=0, le=3)
    context_expansion: Literal["none", "adjacent", "section"] = "adjacent"
    section_summarize_threshold_chars: int = Field(default=6_000, ge=500, le=200_000)
    section_max_context_chars: int = Field(default=4_000, ge=500, le=200_000)

    max_attached_fragments: int = Field(default=10, ge=1, le=200)

    max_context_chars: int = Field(default=12_000, ge=1_000, le=50_000)
    reduction_batch_chars: int = Field(default=6_000, ge=1_000, le=20_000)
    reduction_max_passes: int = Field(default=2, ge=1, le=5)

    max_response_chars: int = Field(default=MAX_CONTENT_CHARS, ge=1_000, le=MAX_CONTENT_CHARS)

    def to_generation_settings(self) -> GenerationSettings:
        return GenerationSettings(
            history_messages_window=self.history_messages_window,
            max_context_chars=self.max_context_chars,
            max_context_tokens=chars_to_tokens(self.max_context_chars),
        )

    def to_reformulation_settings(self) -> QueryReformulationSettings:
        return QueryReformulationSettings(
            history_messages_window=self.history_messages_window,
            rewrite_query=self.rewrite_query,
            use_keywords=self.use_keywords,
        )

    def to_retrieval_settings(self) -> ContextRetrievalSettings:
        overrides: dict = {
            "semantic_fragments_per_lane": self.semantic_fragments_per_lane,
            "bm25_fragments_per_lane": self.bm25_fragments_per_lane,
            "use_rerank": self.use_rerank,
            "adjacent_chunks": self.adjacent_chunks,
            "context_expansion": self.context_expansion,
            "max_context_chars": self.max_context_chars,
        }
        if self.use_rerank:
            overrides["max_fragments"] = self.rerank_max_fragments
        return ContextRetrievalSettings(**overrides)

    def to_section_settings(self) -> SectionContextSettings:
        return SectionContextSettings(
            summarize_threshold_chars=self.section_summarize_threshold_chars,
            max_section_context_chars=self.section_max_context_chars,
        )

    def to_attached_settings(self) -> AttachedDocumentsSettings:
        return AttachedDocumentsSettings(max_fragments=self.max_attached_fragments)

    def to_reduction_settings(self) -> ContextReductionSettings:
        return ContextReductionSettings(
            max_batch_chars=self.reduction_batch_chars,
            max_passes=self.reduction_max_passes,
            max_context_chars=self.max_context_chars,
        )
