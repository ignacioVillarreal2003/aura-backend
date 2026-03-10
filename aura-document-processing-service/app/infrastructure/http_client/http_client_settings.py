import logging
from typing import Dict, Optional

from pydantic import Field, model_validator, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class HttpClientSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HTTP_CLIENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    default_timeout_seconds: float = Field(
        default=30.0,
        gt=0,
        le=300.0
    )
    tcp_connect_timeout_seconds: float = Field(
        default=10.0,
        gt=0,
        le=60.0
    )
    socket_read_timeout_seconds: float = Field(
        default=30.0,
        gt=0,
        le=300.0
    )
    socket_write_timeout_seconds: float = Field(
        default=60.0,
        gt=0,
        le=600.0
    )

    retry_max_attempts: int = Field(
        default=3,
        ge=0,
        le=10
    )
    retry_backoff_min_seconds: float = Field(
        default=1.0,
        gt=0,
        le=30.0
    )
    retry_backoff_max_seconds: float = Field(
        default=10.0,
        gt=0,
        le=60.0
    )

    circuit_breaker_failure_threshold: int = Field(
        default=5,
        ge=1,
        le=20
    )
    circuit_breaker_recovery_timeout_seconds: int = Field(
        default=60,
        gt=0,
        le=600
    )

    connection_pool_max_size: int = Field(
        default=100,
        gt=0,
        le=1000
    )
    connection_pool_max_keepalive: int = Field(
        default=20,
        gt=0,
        le=100
    )

    ssl_verify_certificates: bool = Field(
        default=True
    )
    follow_http_redirects: bool = Field(
        default=True
    )

    request_user_agent: str = Field(
        default="app/1.0"
    )
    request_default_headers: Optional[Dict[str, str]] = Field(
        default=None
    )

    metrics_enabled: bool = Field(
        default=True
    )

    @field_validator(
        "request_default_headers",
        mode="before"
    )
    @classmethod
    def empty_string_to_none(
            cls,
            v
    ):
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @model_validator(
        mode="after"
    )
    def validate_configuration_coherence(self) -> "HttpClientSettings":
        if self.retry_backoff_min_seconds >= self.retry_backoff_max_seconds:
            raise ValueError(
                f"retry_backoff_min_seconds ({self.retry_backoff_min_seconds}s) must be "
                f"strictly less than retry_backoff_max_seconds ({self.retry_backoff_max_seconds}s)"
            )

        if self.connection_pool_max_keepalive > self.connection_pool_max_size:
            raise ValueError(
                f"connection_pool_max_keepalive ({self.connection_pool_max_keepalive}) "
                f"cannot exceed connection_pool_max_size ({self.connection_pool_max_size})"
            )

        if self.tcp_connect_timeout_seconds >= self.socket_read_timeout_seconds:
            logger.warning(
                "tcp_connect_timeout_seconds is not less than socket_read_timeout_seconds",
                extra={
                    "tcp_connect_timeout_seconds": self.tcp_connect_timeout_seconds,
                    "socket_read_timeout_seconds": self.socket_read_timeout_seconds
                }
            )

        if self.socket_read_timeout_seconds >= self.socket_write_timeout_seconds:
            logger.warning(
                "socket_read_timeout_seconds is not less than socket_write_timeout_seconds"
                " — large request bodies may time out",
                extra={
                    "socket_read_timeout_seconds": self.socket_read_timeout_seconds,
                    "socket_write_timeout_seconds": self.socket_write_timeout_seconds
                }
            )

        return self

    @property
    def merged_request_headers(self) -> Dict[str, str]:
        base: Dict[str, str] = {
            "User-Agent": self.request_user_agent
        }
        if self.request_default_headers:
            base.update(self.request_default_headers)
        return base

    def get_httpx_timeout(self) -> dict:
        return {
            "timeout": self.default_timeout_seconds,
            "connect": self.tcp_connect_timeout_seconds,
            "read": self.socket_read_timeout_seconds,
            "write": self.socket_write_timeout_seconds
        }

    def get_httpx_limits(self) -> dict:
        return {
            "max_connections": self.connection_pool_max_size,
            "max_keepalive_connections": self.connection_pool_max_keepalive
        }
