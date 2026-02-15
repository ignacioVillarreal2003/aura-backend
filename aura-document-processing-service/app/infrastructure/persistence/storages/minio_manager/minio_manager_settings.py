import logging
from typing import Optional
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class MinioManagerSettings(BaseSettings):
    endpoint: str = Field(
        ...,
        description="MinIO endpoint (e.g., 'localhost:9000' or 'minio.example.com')"
    )
    access_key: str = Field(
        ...,
        description="MinIO access key"
    )
    secret_key: SecretStr = Field(
        ...,
        description="MinIO secret key"
    )
    secure: bool = Field(
        default=True,
        description="Use HTTPS for connections"
    )
    region: str = Field(
        default="us-east-1",
        description="MinIO region"
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
    retry_backoff_multiplier: float = Field(
        default=1.0,
        gt=0,
        le=10.0,
        description="Multiplier for exponential backoff"
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

    max_pool_connections: int = Field(
        default=10,
        gt=0,
        le=100,
        description="Maximum number of pooled connections"
    )

    presigned_url_expiry: int = Field(
        default=3600,
        gt=0,
        le=604800,
        description="Default expiry time for presigned URLs in seconds"
    )

    multipart_threshold: int = Field(
        default=5 * 1024 * 1024,  # 5MB
        gt=0,
        description="Minimum file size in bytes to use multipart upload"
    )
    multipart_chunksize: int = Field(
        default=5 * 1024 * 1024,
        gt=0,
        description="Chunk size in bytes for multipart uploads"
    )

    enable_metrics: bool = Field(
        default=True,
        description="Enable metrics collection"
    )
    enable_health_check: bool = Field(
        default=True,
        description="Enable periodic health checks"
    )

    default_bucket: Optional[str] = Field(
        default=None,
        description="Default bucket name if not specified in operations"
    )
    auto_create_bucket: bool = Field(
        default=False,
        description="Automatically create bucket if it doesn't exist"
    )

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(
            cls,
            v: str
    ) -> str:
        if not v or not v.strip():
            raise ValueError("Endpoint cannot be empty")

        v = v.strip()

        if v.startswith(("http://", "https://")):
            raise ValueError(
                "Endpoint should not include protocol. "
                "Use 'secure' parameter to control HTTP/HTTPS"
            )

        try:
            parsed = urlparse(f"http://{v}")
            if not parsed.netloc:
                raise ValueError(f"Invalid endpoint format: {v}")
        except Exception as e:
            raise ValueError(f"Invalid endpoint: {v}") from e

        return v

    @field_validator("access_key")
    @classmethod
    def validate_access_key(
            cls,
            v: str
    ) -> str:
        if not v or not v.strip():
            raise ValueError("Access key cannot be empty")

        v = v.strip()

        if len(v) < 3:
            raise ValueError("Access key must be at least 3 characters")

        return v

    @field_validator("region")
    @classmethod
    def validate_region(
            cls,
            v: str
    ) -> str:
        if not v or not v.strip():
            raise ValueError("Region cannot be empty")

        return v.strip()

    @field_validator("default_bucket")
    @classmethod
    def validate_bucket_name(
            cls,
            v: Optional[str]
    ) -> Optional[str]:
        if v is None:
            return v

        v = v.strip()

        if len(v) < 3 or len(v) > 63:
            raise ValueError("Bucket name must be between 3 and 63 characters")

        if not v[0].isalnum() or not v[-1].isalnum():
            raise ValueError("Bucket name must start and end with letter or number")

        import re
        if not re.match(r'^[a-z0-9][a-z0-9.-]*[a-z0-9]$', v):
            raise ValueError(
                "Bucket name can only contain lowercase letters, numbers, dots, and hyphens"
            )

        if '..' in v or '.-' in v or '-.' in v:
            raise ValueError("Bucket name cannot contain consecutive special characters")

        return v

    @model_validator(
        mode='after'
    )
    def validate_timeouts(
            self
    ) -> 'MinioManagerSettings':
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
    ) -> 'MinioManagerSettings':
        if self.retry_backoff_min >= self.retry_backoff_max:
            raise ValueError(
                f"retry_backoff_min ({self.retry_backoff_min}) must be less than "
                f"retry_backoff_max ({self.retry_backoff_max})"
            )

        return self

    @model_validator(
        mode='after'
    )
    def validate_multipart_settings(
            self
    ) -> 'MinioManagerSettings':
        min_part_size = 5 * 1024 * 1024

        if self.multipart_chunksize < min_part_size:
            logger.warning(
                f"multipart_chunksize ({self.multipart_chunksize} bytes) is below "
                f"recommended minimum ({min_part_size} bytes). Setting to minimum."
            )
            object.__setattr__(self, 'multipart_chunksize', min_part_size)

        if self.multipart_threshold < min_part_size:
            logger.warning(
                f"multipart_threshold ({self.multipart_threshold} bytes) is below "
                f"recommended minimum ({min_part_size} bytes)."
            )

        return self

    @property
    def endpoint_url(
            self
    ) -> str:
        protocol = "https" if self.secure else "http"
        return f"{protocol}://{self.endpoint}"

    @property
    def endpoint_safe(
            self
    ) -> str:
        return f"{self.endpoint} (secure={self.secure})"

    def get_boto3_config(
            self
    ) -> dict:
        return {
            'aws_access_key_id': self.access_key,
            'aws_secret_access_key': self.secret_key.get_secret_value(),
            'endpoint_url': self.endpoint_url,
            'region_name': self.region,
            'config': {
                'signature_version': 's3v4',
                'connect_timeout': self.connect_timeout,
                'read_timeout': self.read_timeout,
                'retries': {
                    'max_attempts': self.max_retries,
                    'mode': 'adaptive'
                },
                'max_pool_connections': self.max_pool_connections,
            }
        }

    def get_minio_config(
            self
    ) -> dict:
        return {
            'endpoint': self.endpoint,
            'access_key': self.access_key,
            'secret_key': self.secret_key.get_secret_value(),
            'secure': self.secure,
            'region': self.region,
        }
