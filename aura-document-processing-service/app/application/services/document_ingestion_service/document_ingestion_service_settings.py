import logging
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings

from app.application.processors.embedders.constants.embedder_type import EmbedderType
from app.application.processors.text_cleaners.constants.text_cleaner_type import TextCleanerType
from app.application.processors.text_splitters.constants.text_splitter_type import TextSplitterType

logger = logging.getLogger(__name__)


class DocumentIngestionServiceSettings(BaseSettings):
    split_size: int = Field(
        default=1000,
        gt=0,
        le=100000,
        description="Size of text chunks"
    )
    split_overlap: int = Field(
        default=200,
        ge=0,
        description="Overlap between chunks"
    )

    text_cleaner_type: TextCleanerType = Field(
        default=TextCleanerType.space,
        description="Text cleaning method"
    )
    text_splitter_type: TextSplitterType = Field(
        default=TextSplitterType.recursive,
        description="Text splitting method"
    )
    embedder_type: EmbedderType = Field(
        default=EmbedderType.ollama,
        description="Embedding method"
    )

    enable_background_processing: bool = Field(
        default=True,
        description="Enable background processing"
    )
    cleanup_temp_files: bool = Field(
        default=True,
        description="Automatically cleanup temporary files after processing"
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum retry attempts for failed operations"
    )

    batch_size: int = Field(
        default=100,
        gt=0,
        le=1000,
        description="Batch size for fragment processing"
    )
    enable_parallel_processing: bool = Field(
        default=False,
        description="Enable parallel processing of documents"
    )

    enable_metrics: bool = Field(
        default=True,
        description="Enable metrics collection"
    )

    @field_validator("split_size")
    @classmethod
    def validate_split_size(
            cls,
            v: int
    ) -> int:
        if v < 1:
            raise ValueError("split_size must be at least 1")
        if v > 100000:
            raise ValueError("split_size cannot exceed 100,000")
        return v

    @field_validator("split_overlap")
    @classmethod
    def validate_split_overlap(
            cls,
            v: int
    ) -> int:
        if v < 0:
            raise ValueError("split_overlap cannot be negative")
        return v

    @model_validator(
        mode='after'
    )
    def validate_overlap_less_than_size(
            self
    ) -> 'DocumentIngestionServiceSettings':
        if self.split_overlap >= self.split_size:
            raise ValueError(
                f"split_overlap ({self.split_overlap}) must be less than "
                f"split_size ({self.split_size})"
            )
        return self

    @field_validator("text_cleaner_type")
    @classmethod
    def validate_text_cleaner_type(
            cls,
            v: str
    ) -> str:
        allowed = {e.value for e in TextCleanerType}
        if v not in allowed:
            raise ValueError(
                f"text_cleaner_type must be one of {sorted(allowed)}, got: {v}"
            )
        return v

    @field_validator("text_splitter_type")
    @classmethod
    def validate_text_splitter_type(
            cls,
            v: str
    ) -> str:
        allowed = {e.value for e in TextSplitterType}
        if v not in allowed:
            raise ValueError(
                f"text_splitter_type must be one of {sorted(allowed)}, got: {v}"
            )
        return v

    @field_validator("embedder_type")
    @classmethod
    def validate_embedder_type(
            cls,
            v: str
    ) -> str:
        allowed = {e.value for e in EmbedderType}
        if v not in allowed:
            raise ValueError(f"embedder_type must be one of {sorted(allowed)}, got: {v}")
        return v

    @field_validator("batch_size")
    @classmethod
    def validate_batch_size(
            cls,
            v: int
    ) -> int:
        if v < 1:
            raise ValueError("batch_size must be at least 1")
        if v > 1000:
            raise ValueError("batch_size cannot exceed 1000")
        return v
