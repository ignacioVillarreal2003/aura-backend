import logging
from typing import Optional
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.application.services.document_summary_service.constants.summarization_strategy import SummarizationStrategy

logger = logging.getLogger(__name__)


class DocumentSummaryServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DOCUMENT_SUMMARY_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    large_document_threshold: int = Field(default=5, ge=2, le=50)

    chunk_size: int = Field(default=5, ge=1, le=20)
    max_concurrent_chunks: int = Field(default=3, ge=1, le=10)

    max_retry_attempts: int = Field(default=3, ge=0, le=10)
    retry_delay: float = Field(default=1.0, ge=0.0, le=60.0)

    custom_system_prompt: Optional[str] = Field(default=None)

    _DEFAULT_SYSTEM_PROMPT: str = (
        "You are an expert assistant specialized in creating accurate and concise summaries "
        "based exclusively on the provided content.\n\n"
        "STRICT RULES:\n"
        "1. Summarize ONLY using information present in the provided content.\n"
        "2. Do NOT add, infer, or assume information not explicitly in the text.\n"
        "3. If a section of the content does not contribute relevant information, omit it.\n"
        "4. Prioritize key points, main concepts, and important conclusions.\n"
        "5. Keep the summary clear, structured, and easy to read.\n"
        "6. Use Markdown formatting: headings (#), subheadings (##), lists (-), "
        "bold (**), tables where appropriate.\n"
        "7. Be concise without losing essential information.\n"
    )

    @model_validator(mode="after")
    def validate_coherence(self) -> "DocumentSummaryServiceSettings":
        if self.chunk_size > self.large_document_threshold:
            logger.warning(
                "chunk_size exceeds large_document_threshold — "
                "MAP_REDUCE will never produce more than one chunk",
                extra={
                    "chunk_size": self.chunk_size,
                    "large_document_threshold": self.large_document_threshold
                }
            )
        return self

    def select_strategy(self, fragment_count: int) -> SummarizationStrategy:
        if fragment_count > self.large_document_threshold:
            return SummarizationStrategy.map_reduce
        return SummarizationStrategy.direct

    @property
    def system_prompt(self) -> str:
        return self.custom_system_prompt or self._DEFAULT_SYSTEM_PROMPT
