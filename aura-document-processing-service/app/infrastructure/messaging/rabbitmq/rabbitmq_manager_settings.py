from typing import Optional

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RabbitMQManagerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RABBITMQ_MANAGER_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    url: SecretStr = Field(...)

    tcp_connect_timeout_seconds: float = Field(default=10.0, gt=0, le=60.0)

    heartbeat_seconds: int = Field(
        default=60,
        ge=10,
        le=900,
        description="AMQP heartbeat interval in seconds (passed to the broker connection).",
    )
    blocked_connection_timeout_seconds: Optional[float] = Field(
        default=300.0,
        gt=0,
        le=3600.0,
        description="Seconds before the broker treats this connection as blocked; None to omit.",
    )
    client_connection_name: str = Field(
        default="aura-document-processing-service",
        max_length=128,
        description="Shown in the RabbitMQ management UI for this connection.",
    )

    retry_max_attempts: int = Field(default=3, ge=1, le=10)
    retry_backoff_min_seconds: float = Field(default=1.0, gt=0, le=30.0)
    retry_backoff_max_seconds: float = Field(default=10.0, gt=0, le=60.0)
    publish_timeout_seconds: float = Field(default=10.0, gt=0, le=60.0)

    prefetch_count: int = Field(default=5, ge=1, le=100)

    max_delivery_attempts: int = Field(default=3, ge=1, le=20)

    consumer_reconnect_delay_seconds: float = Field(default=5.0, gt=0, le=60.0)

    max_message_body_bytes: int = Field(
        default=16_777_216,
        ge=1024,
        le=536_870_912,
        description="Maximum inbound message body size accepted by consumers before JSON decode.",
    )

    message_ttl_ms: Optional[int] = Field(default=None, ge=1000)

    exchange: str = Field(default="aura")
    dlx_exchange: str = Field(default="aura.dlx")
    dlq_queue: str = Field(default="aura.dead")

    document_ingestion_queue: str = Field(default="document.ingestion")
    graph_extraction_queue: str = Field(default="graph.extraction")
    document_enrichment_queue: str = Field(default="document.enrichment")
    document_purge_queue: str = Field(default="document.purge")
    document_reembed_queue: str = Field(default="document.reembed")
    document_reprocess_queue: str = Field(default="document.reprocess")

    document_ingestion_lock_ttl_seconds: int = Field(default=1800, ge=60, le=86400)
    document_ingestion_lock_key_prefix: str = Field(default="aura:ingestion", max_length=128)
    document_ingestion_temp_dir_name: str = Field(
        default="doc_ingestion",
        max_length=128,
        description="Subdirectory name under the OS temp dir used for ingestion scratch files.",
    )

    @field_validator(
        "url",
        mode="before"
    )
    @classmethod
    def validate_url(
            cls,
            v: str
    ) -> str:
        v = str(v).strip()
        if not v:
            raise ValueError("The RabbitMQ URL cannot be empty.")
        if not v.startswith(("amqp://", "amqps://")):
            raise ValueError(
                "The RabbitMQ URL must start with amqp:// for plain connections or amqps:// for TLS."
            )
        return v

    @field_validator(
        "exchange",
        "document_ingestion_queue",
        "graph_extraction_queue",
        "document_enrichment_queue",
        "document_purge_queue",
        "document_reembed_queue",
        "document_reprocess_queue",
        "dlx_exchange",
        "dlq_queue",
        mode="before"
    )
    @classmethod
    def validate_name(
            cls,
            v: str
    ) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Exchange and queue names cannot be empty.")
        return v

    @model_validator(
        mode="after"
    )
    def validate_backoff(self) -> "RabbitMQManagerSettings":
        if self.retry_backoff_min_seconds >= self.retry_backoff_max_seconds:
            raise ValueError("The shortest retry wait must be less than the longest retry wait.")
        return self

    @property
    def url_safe(
            self
    ) -> str:
        raw = self.url.get_secret_value()
        try:
            from urllib.parse import urlparse

            parsed = urlparse(raw)
            host = f"{parsed.hostname}:{parsed.port}" if parsed.port else parsed.hostname
            return f"{parsed.scheme}://***:***@{host}{parsed.path}"
        except Exception:
            return "amqp://<redacted>"
