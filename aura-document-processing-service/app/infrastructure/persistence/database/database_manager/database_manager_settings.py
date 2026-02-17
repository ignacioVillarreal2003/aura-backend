import logging
from pathlib import Path
from urllib.parse import quote_plus
from typing import Optional
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class DatabaseManagerSettings(BaseSettings):
    driver: str = Field(
        default="asyncpg",
        description="Database driver (currently only postgresql supported)"
    )
    user: str = Field(
        ...,
        description="Database user"
    )
    password: SecretStr = Field(
        ...,
        description="Database password"
    )
    host: str = Field(
        ...,
        description="Database host"
    )
    port: int = Field(
        default=5432,
        ge=1,
        le=65535,
        description="Database port"
    )
    name: str = Field(
        ...,
        description="Database name"
    )

    pool_size: int = Field(
        default=10,
        gt=0,
        le=100,
        description="Number of connections to maintain in the pool"
    )
    max_overflow: int = Field(
        default=20,
        ge=0,
        le=100,
        description="Maximum number of connections to create beyond pool_size"
    )
    pool_recycle: int = Field(
        default=3600,
        gt=0,
        description="Recycle connections after this many seconds (prevents stale connections)"
    )
    pool_pre_ping: bool = Field(
        default=True,
        description="Test connections for liveness before using them"
    )
    pool_timeout: float = Field(
        default=30.0,
        gt=0,
        le=300.0,
        description="Seconds to wait before giving up on getting a connection from the pool"
    )

    connect_timeout: int = Field(
        default=10,
        gt=0,
        le=60,
        description="Database connection timeout in seconds"
    )
    statement_timeout: int = Field(
        default=30,
        gt=0,
        le=300,
        description="Maximum time in seconds for a single SQL statement to execute"
    )

    application_name: str = Field(
        default="aura-document-processing-service",
        description="Application name for database connection tracking"
    )

    echo: bool = Field(
        default=False,
        description="Enable SQLAlchemy engine logging"
    )
    enable_query_logging: bool = Field(
        default=False,
        description="Enable detailed query logging (use only in development)"
    )

    ssl_mode: Optional[str] = Field(
        default=None,
        description="SSL mode: disable, allow, prefer, require, verify-ca, verify-full"
    )
    ssl_cert_path: Optional[Path] = Field(
        default=None,
        description="Path to SSL certificate file"
    )
    ssl_key_path: Optional[Path] = Field(
        default=None,
        description="Path to SSL key file"
    )
    ssl_root_cert_path: Optional[Path] = Field(
        default=None,
        description="Path to SSL root certificate file"
    )

    @field_validator("driver")
    @classmethod
    def validate_driver(
            cls,
            v: str
    ) -> str:
        allowed = ["postgresql", "postgresql+asyncpg"]
        if v not in allowed:
            raise ValueError(f"Driver must be one of {allowed}, got: {v}")
        return v

    @field_validator("ssl_mode")
    @classmethod
    def validate_ssl_mode(
            cls,
            v: Optional[str]
    ) -> Optional[str]:
        if v is None:
            return v

        allowed = ["disable", "allow", "prefer", "require", "verify-ca", "verify-full"]
        if v not in allowed:
            raise ValueError(f"SSL mode must be one of {allowed}, got: {v}")
        return v

    @field_validator("ssl_cert_path", "ssl_key_path", "ssl_root_cert_path")
    @classmethod
    def validate_ssl_path(
            cls,
            v: Optional[Path]
    ) -> Optional[Path]:
        if v is not None and not v.exists():
            raise ValueError(f"SSL file not found: {v}")
        return v

    @model_validator(mode='after')
    def validate_pool_settings(
            self
    ) -> 'DatabaseManagerSettings':
        total_connections = self.pool_size + self.max_overflow

        if total_connections > 100:
            logger.warning(
                f"Total connections ({total_connections}) may exceed recommended PostgreSQL limits. "
                f"Consider reducing pool_size or max_overflow."
            )

        if self.pool_timeout < self.connect_timeout:
            logger.warning(
                f"pool_timeout ({self.pool_timeout}s) is less than connect_timeout ({self.connect_timeout}s). "
                f"This may cause premature timeout errors."
            )

        return self

    @model_validator(mode='after')
    def validate_ssl_configuration(
            self
    ) -> 'DatabaseManagerSettings':
        ssl_fields = [self.ssl_cert_path, self.ssl_key_path, self.ssl_root_cert_path]
        ssl_fields_set = [f for f in ssl_fields if f is not None]

        if ssl_fields_set and len(ssl_fields_set) < len(ssl_fields):
            logger.warning(
                "Incomplete SSL configuration. For full SSL support, provide all: "
                "ssl_cert_path, ssl_key_path, ssl_root_cert_path"
            )

        if ssl_fields_set and self.ssl_mode is None:
            logger.info("SSL certificates provided but ssl_mode not set. Defaulting to 'require'")
            self.ssl_mode = "require"

        return self

    @property
    def url(
            self
    ) -> str:
        password = quote_plus(self.password.get_secret_value())
        driver = f"{self.driver}+asyncpg" if self.driver == "postgresql" else self.driver

        url = f"{driver}://{self.user}:{password}@{self.host}:{self.port}/{self.name}"

        if self.ssl_mode:
            url += f"?ssl={self.ssl_mode}"

            if self.ssl_cert_path:
                url += f"&sslcert={self.ssl_cert_path}"
            if self.ssl_key_path:
                url += f"&sslkey={self.ssl_key_path}"
            if self.ssl_root_cert_path:
                url += f"&sslrootcert={self.ssl_root_cert_path}"

        return url

    @property
    def url_safe(
            self
    ) -> str:
        base_url = f"{self.driver}://{self.user}:***@{self.host}:{self.port}/{self.name}"

        if self.ssl_mode:
            base_url += f" (SSL: {self.ssl_mode})"

        return base_url

    def get_connect_args(
            self
    ) -> dict:
        args = {
            "timeout": self.connect_timeout,
            "command_timeout": self.statement_timeout,
            "server_settings": {
                "application_name": self.application_name,
                "jit": "off",
            },
        }

        if self.ssl_mode and self.ssl_mode != "disable":
            ssl_context = {}

            if self.ssl_cert_path:
                ssl_context["cert"] = str(self.ssl_cert_path)
            if self.ssl_key_path:
                ssl_context["key"] = str(self.ssl_key_path)
            if self.ssl_root_cert_path:
                ssl_context["ca"] = str(self.ssl_root_cert_path)

            if ssl_context:
                args["ssl"] = ssl_context

        return args
