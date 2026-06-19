import logging
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class DocumentIngestionServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DOCUMENT_INGESTION_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    max_raw_text_length: int = Field(default=50_000_000, gt=0)
    min_chunks_required: int = Field(default=1, ge=1)

    # Defensive ceiling on how many chunks a single document may produce. The
    # embedder batches the forward passes internally, but the resulting vector
    # list is accumulated in full before persistence, so an unbounded chunk count
    # risks excessive memory use. Embedding is all-or-nothing (partial persistence
    # would leave gaps in the contiguous fragment_index), so an oversized document
    # is failed fast here rather than risking an OOM mid-embed.
    max_chunks_per_document: int = Field(default=10_000, ge=1)

    @model_validator(
        mode="after"
    )
    def validate_coherence(
            self
    ) -> "DocumentIngestionServiceSettings":
        if self.min_chunks_required < 1:
            raise ValueError("min_chunks_required must be at least 1")
        return self
