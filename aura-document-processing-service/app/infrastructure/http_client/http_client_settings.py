import logging
from typing import Optional, Dict
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class HttpClientSettings(BaseSettings):
    timeout: float = Field(
        default=30.0,
        gt=0,
        le=300.0,
        description="Default timeout for HTTP requests in seconds"
    )
    connect_timeout: float = Field(
        default=10.0,
        gt=0,
        le=60.0,
        description="Connection timeout in seconds"
    )
    read_timeout: float = Field(
        default=30.0,
        gt=0,
        le=300.0,
        description="Read timeout in seconds"
    )
    write_timeout: float = Field(
        default=60.0,
        gt=0,
        le=600.0,
        description="Write timeout in seconds"
    )

    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum number of retry attempts"
    )
    retry_backoff_min: float = Field(
        default=1.0,
        gt=0,
        le=30.0,
        description="Minimum wait time between retries in seconds"
    )
    retry_backoff_max: float = Field(
        default=10.0,
        gt=0,
        le=60.0,
        description="Maximum wait time between retries in seconds"
    )

    circuit_breaker_failures: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of failures before opening circuit breaker"
    )
    circuit_breaker_timeout: int = Field(
        default=60,
        gt=0,
        le=600,
        description="Circuit breaker timeout in seconds"
    )

    max_connections: int = Field(
        default=100,
        gt=0,
        le=1000,
        description="Maximum number of concurrent connections"
    )
    max_keepalive_connections: int = Field(
        default=20,
        gt=0,
        le=100,
        description="Maximum number of keepalive connections"
    )

    verify_ssl: bool = Field(
        default=True,
        description="Verify SSL certificates"
    )
    follow_redirects: bool = Field(
        default=True,
        description="Follow HTTP redirects"
    )

    default_headers: Optional[Dict[str, str]] = Field(
        default=None,
        description="Default headers to include in all requests"
    )

    user_agent: str = Field(
        default="aura-document-processing-service/1.0",
        description="User-Agent header value"
    )

    enable_metrics: bool = Field(
        default=True,
        description="Enable metrics collection"
    )

    @field_validator("max_keepalive_connections")
    @classmethod
    def validate_keepalive_connections(
            cls,
            v: int,
            info
    ) -> int:
        max_connections = info.data.get("max_connections", 100)
        if v > max_connections:
            raise ValueError(
                f"max_keepalive_connections ({v}) cannot exceed "
                f"max_connections ({max_connections})"
            )
        return v

    @model_validator(
        mode='after'
    )
    def validate_timeouts(
            self
    ) -> 'HttpClientSettings':
        if self.connect_timeout >= self.read_timeout:
            logger.warning(
                f"connect_timeout ({self.connect_timeout}s) should be less than "
                f"read_timeout ({self.read_timeout}s)"
            )

        if self.read_timeout >= self.write_timeout:
            logger.warning(
                f"read_timeout ({self.read_timeout}s) should be less than "
                f"write_timeout ({self.write_timeout}s) for large uploads"
            )

        return self

    @model_validator(
        mode='after'
    )
    def validate_retry_settings(
            self
    ) -> 'HttpClientSettings':
        if self.retry_backoff_min >= self.retry_backoff_max:
            raise ValueError(
                f"retry_backoff_min ({self.retry_backoff_min}) must be less than "
                f"retry_backoff_max ({self.retry_backoff_max})"
            )

        return self

    @property
    def headers(
            self
    ) -> Dict[str, str]:
        base_headers = {
            "User-Agent": self.user_agent,
        }
        if self.default_headers:
            base_headers.update(self.default_headers)
        return base_headers

    def get_httpx_limits(
            self
    ) -> dict:
        return {
            "max_connections": self.max_connections,
            "max_keepalive_connections": self.max_keepalive_connections,
        }

    def get_httpx_timeout(
            self
    ) -> dict:
        return {
            "timeout": self.timeout,
            "connect": self.connect_timeout,
            "read": self.read_timeout,
            "write": self.write_timeout,
        }
