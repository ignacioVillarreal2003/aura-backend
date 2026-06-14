from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RedisClientSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="REDIS_CLIENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    url: SecretStr = Field(default="redis://127.0.0.1:6379/0")
    max_connections: int = Field(default=20, ge=1, le=200)
    socket_connect_timeout: float = Field(default=5.0, ge=0.5, le=30.0)
    socket_timeout: float = Field(default=10.0, ge=0.5, le=60.0)
    health_check_interval: int = Field(default=30, ge=0, le=300)
    key_prefix: str = Field(default="aura:coordination", max_length=128)
    outbox_pending_ttl_seconds: int = Field(default=604_800, ge=60, le=2_592_000)
    outbox_published_marker_ttl_seconds: int = Field(default=604_800, ge=60, le=2_592_000)
    outbox_retry_batch_size: int = Field(default=100, ge=1, le=1000)
    outbox_max_retry_attempts: int = Field(default=10, ge=1, le=1000)
    outbox_retry_backoff_min_seconds: int = Field(default=2, ge=1, le=600)
    outbox_retry_backoff_max_seconds: int = Field(default=300, ge=1, le=3600)
    outbox_worker_loop_interval_seconds: int = Field(default=15, ge=1, le=3600)
    outbox_document_reconcile_age_seconds: int = Field(default=60, ge=1, le=3600)
    outbox_document_reconcile_batch_size: int = Field(default=100, ge=1, le=1000)

    @model_validator(mode="after")
    def validate_backoff_range(self) -> "RedisClientSettings":
        if self.outbox_retry_backoff_min_seconds >= self.outbox_retry_backoff_max_seconds:
            raise ValueError(
                "outbox_retry_backoff_min_seconds must be less than outbox_retry_backoff_max_seconds."
            )
        return self
