from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.application.services.generation_shared.generation_settings import GenerationSettings
from app.application.services.generation_shared.processors.attached_documents_processor.attached_documents_settings import (
    AttachedDocumentsSettings,
)
from app.application.services.generation_shared.processors.context_reduction_processor.context_reduction_settings import (
    ContextReductionSettings,
)
from app.application.services.generation_shared.token_estimation import chars_to_tokens


class DocumentActionServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DOCUMENT_ACTION_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    max_attached_fragments: int = Field(default=60, ge=1, le=200)
    max_context_chars: int = Field(default=12_000, ge=1_000, le=50_000)
    reduction_max_concurrent: int = Field(default=3, ge=1, le=32)
    reduction_max_passes: int = Field(default=3, ge=1, le=5)

    def to_generation_settings(self) -> GenerationSettings:
        return GenerationSettings(
            history_messages_window=0,  # not conversational
            max_context_chars=self.max_context_chars,
            max_context_tokens=chars_to_tokens(self.max_context_chars),
        )

    def to_attached_settings(self) -> AttachedDocumentsSettings:
        return AttachedDocumentsSettings(max_fragments=self.max_attached_fragments)

    def to_reduction_settings(self) -> ContextReductionSettings:
        return ContextReductionSettings(
            max_context_chars=self.max_context_chars,
            max_concurrent_batches=self.reduction_max_concurrent,
            max_passes=self.reduction_max_passes,
        )
