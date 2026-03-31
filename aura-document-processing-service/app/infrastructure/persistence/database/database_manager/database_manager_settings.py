import logging
import ssl
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class DatabaseManagerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DATABASE_MANAGER_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    driver: str = Field(default="postgresql+asyncpg")
    user: str = Field(...)
    password: SecretStr = Field(...)
    host: str = Field(...)
    port: int = Field(default=5432, ge=1, le=65535)
    name: str = Field(...)

    pool_persistent_connections: int = Field(default=10, gt=0, le=100)
    pool_overflow_connections: int = Field(default=20, ge=0, le=100)
    pool_checkout_timeout_seconds: float = Field(default=30.0, gt=0, le=300.0)
    pool_recycle_seconds: int = Field(default=3600, gt=0)
    pool_liveness_probe: bool = Field(default=True)

    tcp_connect_timeout_seconds: int = Field(default=10, gt=0, le=60)
    query_execution_timeout_seconds: int = Field(default=30, gt=0, le=300)

    # Retry settings — now configurable per environment (was hardcoded in manager)
    retry_max_attempts: int = Field(default=3, ge=1, le=10)
    retry_backoff_min_seconds: float = Field(default=2.0, gt=0, le=30.0)
    retry_backoff_max_seconds: float = Field(default=10.0, gt=0, le=60.0)

    echo_sql: bool = Field(default=False)
    query_logging_enabled: bool = Field(default=False)
    pg_application_name: str = Field(default="app")

    ssl_enabled: bool = Field(default=False)
    ssl_verify_server_certificate: bool = Field(default=True)
    ssl_client_cert_path: Optional[Path] = Field(default=None)
    ssl_client_key_path: Optional[Path] = Field(default=None)
    ssl_ca_cert_path: Optional[Path] = Field(default=None)

    @field_validator("driver", mode="before")
    @classmethod
    def normalise_driver(cls, v: str) -> str:
        if v == "postgresql":
            return "postgresql+asyncpg"
        if v == "postgresql+asyncpg":
            return v
        raise ValueError(
            f"Unsupported driver '{v}'. Only 'postgresql' / 'postgresql+asyncpg' are supported."
        )

    @field_validator(
        "ssl_client_cert_path",
        "ssl_client_key_path",
        "ssl_ca_cert_path",
        mode="before"
    )
    @classmethod
    def validate_ssl_file_exists(cls, v: Optional[Path]) -> Optional[Path]:
        if isinstance(v, str) and not v.strip():
            return None
        if v is not None:
            path = Path(v)
            if not path.exists():
                raise ValueError(f"SSL file not found: {path}")
            return path
        return v

    @model_validator(mode="after")
    def validate_coherence(self) -> "DatabaseManagerSettings":
        total = self.pool_persistent_connections + self.pool_overflow_connections
        if total > 100:
            logger.warning(
                "Total connection limit may exceed recommended PostgreSQL defaults",
                extra={
                    "persistent": self.pool_persistent_connections,
                    "overflow": self.pool_overflow_connections,
                    "total": total
                }
            )

        if self.pool_checkout_timeout_seconds < self.tcp_connect_timeout_seconds:
            logger.warning(
                "pool_checkout_timeout_seconds is shorter than tcp_connect_timeout_seconds "
                "— pool may give up before the TCP handshake completes",
                extra={
                    "pool_checkout_timeout_seconds": self.pool_checkout_timeout_seconds,
                    "tcp_connect_timeout_seconds": self.tcp_connect_timeout_seconds
                }
            )

        if self.retry_backoff_min_seconds >= self.retry_backoff_max_seconds:
            raise ValueError(
                f"retry_backoff_min_seconds ({self.retry_backoff_min_seconds}s) must be "
                f"strictly less than retry_backoff_max_seconds ({self.retry_backoff_max_seconds}s)"
            )

        if self.ssl_enabled:
            mutual_tls = [self.ssl_client_cert_path, self.ssl_client_key_path]
            if any(mutual_tls) and not all(mutual_tls):
                raise ValueError(
                    "Incomplete mutual-TLS configuration: "
                    "ssl_client_cert_path and ssl_client_key_path must both be set."
                )

        return self

    @property
    def url(self) -> str:
        password = quote_plus(self.password.get_secret_value())
        return f"{self.driver}://{self.user}:{password}@{self.host}:{self.port}/{self.name}"

    @property
    def url_safe(self) -> str:
        ssl_suffix = " (SSL)" if self.ssl_enabled else ""
        return f"{self.driver}://{self.user}:***@{self.host}:{self.port}/{self.name}{ssl_suffix}"

    def get_connect_args(self) -> dict:
        args: dict = {
            "timeout": self.tcp_connect_timeout_seconds,
            "command_timeout": self.query_execution_timeout_seconds,
            "server_settings": {
                "application_name": self.pg_application_name,
                "jit": "off"
            }
        }
        if self.ssl_enabled:
            args["ssl"] = self._build_ssl_context()
        return args

    def _build_ssl_context(self) -> ssl.SSLContext:
        if self.ssl_ca_cert_path:
            ctx = ssl.create_default_context(
                purpose=ssl.Purpose.SERVER_AUTH,
                cafile=str(self.ssl_ca_cert_path)
            )
        else:
            ctx = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)

        if not self.ssl_verify_server_certificate:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

        if self.ssl_client_cert_path and self.ssl_client_key_path:
            ctx.load_cert_chain(
                certfile=str(self.ssl_client_cert_path),
                keyfile=str(self.ssl_client_key_path)
            )

        return ctx
