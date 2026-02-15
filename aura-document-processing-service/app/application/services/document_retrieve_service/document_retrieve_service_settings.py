import logging
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

from app.application.processors.embedders.constants.embedder_type import EmbedderType

logger = logging.getLogger(__name__)


class DocumentRetrieveServiceSettings(BaseSettings):
    embedder_type: EmbedderType = Field(
        default=EmbedderType.ollama,
        description="Embedding method to use"
    )

    default_max_fragments: int = Field(
        default=5,
        gt=0,
        le=100,
        description="Default maximum fragments to retrieve"
    )
    max_fragments_limit: int = Field(
        default=50,
        gt=0,
        le=100,
        description="Maximum allowed fragments in single query"
    )

    enable_caching: bool = Field(
        default=False,
        description="Enable embedding caching"
    )
    cache_ttl_seconds: int = Field(
        default=300,
        gt=0,
        le=3600,
        description="Cache TTL in seconds"
    )

    enable_metrics: bool = Field(
        default=True,
        description="Enable metrics collection"
    )

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

    @field_validator("default_max_fragments")
    @classmethod
    def validate_default_max_fragments(
            cls,
            v: int
    ) -> int:
        if v < 1:
            raise ValueError("default_max_fragments must be at least 1")
        if v > 100:
            raise ValueError("default_max_fragments cannot exceed 100")
        return v

    @field_validator("max_fragments_limit")
    @classmethod
    def validate_max_fragments_limit(
            cls,
            v: int
    ) -> int:
        if v < 1:
            raise ValueError("max_fragments_limit must be at least 1")
        if v > 100:
            raise ValueError("max_fragments_limit cannot exceed 100")
        return v
