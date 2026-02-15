import logging
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class DocumentQueryServiceSettings(BaseSettings):
    default_page_size: int = Field(
        default=10,
        gt=0,
        le=100,
        description="Default page size for list queries"
    )
    max_page_size: int = Field(
        default=100,
        gt=0,
        le=1000,
        description="Maximum allowed page size"
    )

    include_deleted: bool = Field(
        default=False,
        description="Include soft-deleted documents in queries"
    )

    enable_caching: bool = Field(
        default=False,
        description="Enable query result caching"
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

    @field_validator("default_page_size")
    @classmethod
    def validate_default_page_size(
            cls,
            v: int
    ) -> int:
        if v < 1:
            raise ValueError("default_page_size must be at least 1")
        if v > 100:
            raise ValueError("default_page_size cannot exceed 100")
        return v

    @field_validator("max_page_size")
    @classmethod
    def validate_max_page_size(
            cls,
            v: int
    ) -> int:
        if v < 1:
            raise ValueError("max_page_size must be at least 1")
        if v > 1000:
            raise ValueError("max_page_size cannot exceed 1000")
        return v
