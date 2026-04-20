import logging
import re
from typing import Any, Optional
from urllib.parse import urlparse
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

_BUCKET_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9.\-]*[a-z0-9]$")
_BUCKET_INVALID_CONSECUTIVE_RE = re.compile(r"\.\.|\.[-]|[-]\.")
_MIN_SIZE = 5 * 1024 * 1024


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

    retry_max_attempts: int = Field(default=3, ge=1, le=10)
    retry_backoff_multiplier: float = Field(default=1.0, gt=0, le=10.0)
    retry_backoff_min_seconds: float = Field(default=1.0, gt=0, le=30.0)
    retry_backoff_max_seconds: float = Field(default=10.0, gt=0, le=60.0)

    presigned_url_expiry_seconds: int = Field(default=3600, gt=0, le=604_800)

    multipart_upload_threshold_bytes: int = Field(default=5 * 1024 * 1024, gt=0)
    multipart_upload_chunk_size_bytes: int = Field(default=5 * 1024 * 1024, gt=0)

    default_bucket_name: Optional[str] = Field(default=None)
    auto_create_bucket_if_missing: bool = Field(default=False)

    object_key_log_suffix_chars: int = Field(default=48, ge=1, le=512)
    list_prefix_log_suffix_chars: int = Field(default=32, ge=1, le=512)

    @field_validator(
        "endpoint",
        mode="before"
    )
    @classmethod
    def validate_endpoint(
            cls,
            v: str
    ) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Enter the MinIO host and port only; the endpoint cannot be empty.")
        if v.startswith(("http://", "https://")):
            raise ValueError(
                "Do not put http:// or https:// in the endpoint. Turn TLS on or off with the use_tls setting instead."
            )
        if not urlparse(f"http://{v}").netloc:
            raise ValueError("The endpoint does not look like a valid host or host:port. Check for typos.")
        return v

    @field_validator(
        "access_key",
        mode="before"
    )
    @classmethod
    def validate_access_key(
            cls,
            v: str
    ) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("The access key must be at least three characters long.")
        return v

    @field_validator(
        "region",
        mode="before"
    )
    @classmethod
    def validate_region(
            cls,
            v: str
    ) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Set a region name for the object storage client; it cannot be empty.")
        return v

    @field_validator(
        "default_bucket_name",
        mode="before"
    )
    @classmethod
    def validate_bucket_name(
            cls,
            v: Optional[str]
    ) -> Optional[str]:
        if v is None:
            return v

        v = v.strip()
        if not v:
            return None

        if not (3 <= len(v) <= 63):
            raise ValueError("The default bucket name must be between 3 and 63 characters long.")

        if not _BUCKET_NAME_RE.match(v):
            raise ValueError(
                "Use only lowercase letters, numbers, dots, and hyphens in the bucket name, "
                "and start and end with a letter or number."
            )

        if _BUCKET_INVALID_CONSECUTIVE_RE.search(v):
            raise ValueError("The bucket name cannot use consecutive dots or mix dots and hyphens in invalid ways.")

        return v

    @field_validator(
        "multipart_upload_chunk_size_bytes",
        mode="after"
    )
    @classmethod
    def validate_chunk_size(
            cls,
            v: int
    ) -> int:
        if v < _MIN_SIZE:
            raise ValueError(
                "Each multipart upload part must be at least 5 MiB; smaller parts are not accepted by S3-compatible APIs."
            )
        return v

    @field_validator(
        "multipart_upload_threshold_bytes",
        mode="after"
    )
    @classmethod
    def validate_multipart_threshold(
            cls,
            v: int
    ) -> int:
        if v < _MIN_SIZE:
            raise ValueError("The multipart upload threshold must be at least 5 MiB.")
        return v

    @model_validator(
        mode="after"
    )
    def validate_coherence(
            self
    ) -> "MinioManagerSettings":
        if self.retry_backoff_min_seconds >= self.retry_backoff_max_seconds:
            raise ValueError("The shortest retry wait must be less than the longest retry wait.")

        if self.tcp_connect_timeout_seconds >= self.socket_read_timeout_seconds:
            logger.warning(
                "The connect timeout is not shorter than the read timeout, so slow work may hit "
                "the read limit in ways that look like connection problems.",
                extra={
                    "tcp_connect_timeout_seconds": self.tcp_connect_timeout_seconds,
                    "socket_read_timeout_seconds": self.socket_read_timeout_seconds
                }
            )

        if self.socket_read_timeout_seconds >= self.socket_write_timeout_seconds:
            logger.warning(
                "The read timeout meets or exceeds the write timeout, so large uploads may fail "
                "on the write side before the read timeout is reached.",
                extra={
                    "socket_read_timeout_seconds": self.socket_read_timeout_seconds,
                    "socket_write_timeout_seconds": self.socket_write_timeout_seconds
                }
            )

        return self

    @property
    def endpoint_url(
            self
    ) -> str:
        protocol = "https" if self.use_tls else "http"
        return f"{protocol}://{self.endpoint}"

    @property
    def endpoint_safe(
            self
    ) -> str:
        return f"{self.endpoint} (tls={self.use_tls})"

    def get_minio_config(
            self
    ) -> dict[str, Any]:
        return {
            "endpoint": self.endpoint,
            "access_key": self.access_key,
            "secret_key": self.secret_key.get_secret_value(),
            "secure": self.use_tls,
            "region": self.region
        }
