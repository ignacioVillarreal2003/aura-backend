import logging
import re
from typing import Optional
from urllib.parse import urlparse
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class MinioManagerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MINIO_MANAGER_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    endpoint: str = Field(...)
    access_key: str = Field(...)
    secret_key: SecretStr = Field(...)
    use_tls: bool = Field(default=False)
    region: str = Field(default="us-east-1")

    connection_pool_size: int = Field(default=10, gt=0, le=100)
    tcp_connect_timeout_seconds: float = Field(default=10.0, gt=0, le=60.0)
    socket_read_timeout_seconds: float = Field(default=30.0, gt=0, le=300.0)
    socket_write_timeout_seconds: float = Field(default=60.0, gt=0, le=600.0)

    retry_max_attempts: int = Field(default=3, ge=0, le=10)
    retry_backoff_multiplier: float = Field(default=1.0, gt=0, le=10.0)
    retry_backoff_min_seconds: float = Field(default=1.0, gt=0, le=30.0)
    retry_backoff_max_seconds: float = Field(default=10.0, gt=0, le=60.0)

    presigned_url_expiry_seconds: int = Field(default=3600, gt=0, le=604_800)

    multipart_upload_threshold_bytes: int = Field(default=5 * 1024 * 1024, gt=0)
    multipart_upload_chunk_size_bytes: int = Field(default=5 * 1024 * 1024, gt=0)

    default_bucket_name: Optional[str] = Field(default=None)
    auto_create_bucket_if_missing: bool = Field(default=False)

    metrics_enabled: bool = Field(default=True)

    @field_validator("endpoint", mode="before")
    @classmethod
    def validate_endpoint(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Endpoint cannot be empty")
        if v.startswith(("http://", "https://")):
            raise ValueError(
                "Endpoint must not include a protocol prefix. "
                "Use 'use_tls' to toggle HTTPS."
            )
        if not urlparse(f"http://{v}").netloc:
            raise ValueError(f"Invalid endpoint format: '{v}'")
        return v

    @field_validator("access_key", mode="before")
    @classmethod
    def validate_access_key(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Access key must be at least 3 characters")
        return v

    @field_validator("region", mode="before")
    @classmethod
    def validate_region(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Region cannot be empty")
        return v

    @field_validator("default_bucket_name", mode="before")
    @classmethod
    def validate_bucket_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v

        v = v.strip()
        if not v:
            return None

        if not (3 <= len(v) <= 63):
            raise ValueError("Bucket name must be between 3 and 63 characters")

        _BUCKET_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9.\-]*[a-z0-9]$")
        if not _BUCKET_NAME_RE.match(v):
            raise ValueError(
                "Bucket name may only contain lowercase letters, numbers, hyphens and dots, "
                "and must start/end with a letter or number"
            )

        _BUCKET_INVALID_CONSECUTIVE_RE = re.compile(r"\.\.|\.[-]|[-]\.")
        if _BUCKET_INVALID_CONSECUTIVE_RE.search(v):
            raise ValueError(
                "Bucket name cannot contain consecutive special characters ('..', '.-', '-.')"
            )

        return v

    @field_validator("multipart_upload_chunk_size_bytes", mode="after")
    @classmethod
    def validate_chunk_size(cls, v: int) -> int:
        min_size = 5 * 1024 * 1024
        if v < min_size:
            raise ValueError(
                f"multipart_upload_chunk_size_bytes ({v}) must be at least "
                f"{min_size} bytes (5 MiB) — S3-compatible APIs reject smaller parts."
            )
        return v

    @field_validator("multipart_upload_threshold_bytes", mode="after")
    @classmethod
    def validate_multipart_threshold(cls, v: int) -> int:
        min_size = 5 * 1024 * 1024
        if v < min_size:
            raise ValueError(
                f"multipart_upload_threshold_bytes ({v}) must be at least "
                f"{min_size} bytes (5 MiB)."
            )
        return v

    @model_validator(mode="after")
    def validate_coherence(self) -> "MinioManagerSettings":
        if self.retry_backoff_min_seconds >= self.retry_backoff_max_seconds:
            raise ValueError(
                f"retry_backoff_min_seconds ({self.retry_backoff_min_seconds}s) must be "
                f"strictly less than retry_backoff_max_seconds ({self.retry_backoff_max_seconds}s)"
            )

        if self.tcp_connect_timeout_seconds >= self.socket_read_timeout_seconds:
            logger.warning(
                "tcp_connect_timeout_seconds is not less than socket_read_timeout_seconds",
                extra={
                    "tcp_connect": self.tcp_connect_timeout_seconds,
                    "socket_read": self.socket_read_timeout_seconds
                }
            )

        if self.socket_read_timeout_seconds >= self.socket_write_timeout_seconds:
            logger.warning(
                "socket_read_timeout_seconds is not less than socket_write_timeout_seconds "
                "— large uploads may time out",
                extra={
                    "socket_read": self.socket_read_timeout_seconds,
                    "socket_write": self.socket_write_timeout_seconds
                }
            )

        return self

    @property
    def endpoint_url(self) -> str:
        protocol = "https" if self.use_tls else "http"
        return f"{protocol}://{self.endpoint}"

    @property
    def endpoint_safe(self) -> str:
        return f"{self.endpoint} (tls={self.use_tls})"

    def get_minio_config(self) -> dict:
        return {
            "endpoint": self.endpoint,
            "access_key": self.access_key,
            "secret_key": self.secret_key.get_secret_value(),
            "secure": self.use_tls,
            "region": self.region
        }
