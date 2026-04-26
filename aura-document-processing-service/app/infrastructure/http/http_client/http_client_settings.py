import logging
from functools import cached_property
from typing import Optional
from pydantic import Field, field_validator, model_validator
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

    timeout_seconds: float = Field(default=30.0, gt=0, le=300.0)
    tcp_connect_timeout_seconds: float = Field(default=10.0, gt=0, le=60.0)
    socket_read_timeout_seconds: float = Field(default=30.0, gt=0, le=300.0)
    socket_write_timeout_seconds: float = Field(default=60.0, gt=0, le=600.0)
    pool_acquire_timeout_seconds: float = Field(default=5.0, gt=0, le=120.0)

    retry_max_attempts: int = Field(default=3, ge=0, le=10)
    retry_backoff_min_seconds: float = Field(default=1.0, gt=0, le=30.0)
    retry_backoff_max_seconds: float = Field(default=10.0, gt=0, le=60.0)
    retry_enabled_http_methods: str = Field(default="GET,HEAD,OPTIONS,PUT")

    circuit_breaker_failure_threshold: int = Field(default=5, ge=1, le=20)
    circuit_breaker_recovery_timeout_seconds: int = Field(default=60, gt=0, le=600)

    connection_pool_max_size: int = Field(default=100, gt=0, le=1000)
    connection_pool_max_keepalive: int = Field(default=20, gt=0, le=100)
    keepalive_expiry_seconds: float = Field(default=5.0, gt=0, le=300.0)

    ssl_verify_certificates: bool = Field(default=True)
    follow_http_redirects: bool = Field(default=True)
    trust_env: bool = Field(default=True)
    use_http2: bool = Field(default=False)

    request_user_agent: str = Field(default="app/1.0")
    request_default_headers: Optional[dict[str, str]] = Field(default=None)

    @field_validator("request_default_headers", mode="before")
    @classmethod
    def empty_string_to_none(cls, v):
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @model_validator(mode="after")
    def validate_coherence(self) -> "HttpClientSettings":
        if self.retry_backoff_min_seconds >= self.retry_backoff_max_seconds:
            raise ValueError("The shortest retry wait must be less than the longest retry wait.")

        if self.connection_pool_max_keepalive > self.connection_pool_max_size:
            raise ValueError("The keep-alive connection limit cannot be greater than the total connection pool size.")

        if self.tcp_connect_timeout_seconds >= self.socket_read_timeout_seconds:
            logger.warning(
                "The connect timeout is not shorter than the read timeout, so slow reads may be "
                "cut off before the connection phase suggests.",
                extra={
                    "tcp_connect_timeout_seconds": self.tcp_connect_timeout_seconds,
                    "socket_read_timeout_seconds": self.socket_read_timeout_seconds
                }
            )

        if self.socket_read_timeout_seconds >= self.socket_write_timeout_seconds:
            logger.warning(
                "The read timeout meets or exceeds the write timeout, so large uploads may hit "
                "the read limit before the write limit.",
                extra={
                    "socket_read_timeout_seconds": self.socket_read_timeout_seconds,
                    "socket_write_timeout_seconds": self.socket_write_timeout_seconds
                }
            )

        return self

    @cached_property
    def retry_enabled_method_set(self) -> frozenset[str]:
        methods = {m.strip().upper() for m in self.retry_enabled_http_methods.split(",") if m.strip()}
        return frozenset(methods)

    @property
    def merged_request_headers(self) -> dict[str, str]:
        base: dict[str, str] = {"User-Agent": self.request_user_agent}
        if self.request_default_headers:
            base.update(self.request_default_headers)
        return base

    def get_httpx_timeout(self) -> dict:
        return {
            "connect": self.tcp_connect_timeout_seconds,
            "read": self.socket_read_timeout_seconds,
            "write": self.socket_write_timeout_seconds,
            "pool": self.pool_acquire_timeout_seconds,
        }

    def get_httpx_limits(self) -> dict:
        return {
            "max_connections": self.connection_pool_max_size,
            "max_keepalive_connections": self.connection_pool_max_keepalive,
            "keepalive_expiry": self.keepalive_expiry_seconds,
        }
