from typing import Optional
from urllib.parse import urlparse
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Neo4jManagerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="NEO4J_MANAGER_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    uri: str = Field(...)
    user: str = Field(..., min_length=1, max_length=128)
    password: SecretStr = Field(...)
    database: str = Field(default="neo4j", min_length=1, max_length=128)

    pool_max_size: int = Field(default=50, ge=1, le=500)
    connection_acquisition_timeout_seconds: float = Field(default=60.0, gt=0, le=600.0)
    connection_timeout_seconds: float = Field(default=15.0, gt=0, le=120.0)
    max_transaction_retry_seconds: float = Field(default=30.0, gt=0, le=300.0)

    encrypted: Optional[bool] = Field(default=None)

    health_probe_timeout_seconds: float = Field(default=5.0, gt=0, le=60.0)

    apply_schema_on_startup: bool = Field(default=True)

    @field_validator("uri", mode="before")
    @classmethod
    def validate_uri(cls, v: str) -> str:
        v = str(v).strip()
        if not v:
            raise ValueError("The Neo4j URI cannot be empty.")
        parsed = urlparse(v)
        scheme = (parsed.scheme or "").lower()
        if scheme not in ("neo4j", "neo4j+s", "neo4j+ssc", "bolt", "bolt+s", "bolt+ssc"):
            raise ValueError(
                "The Neo4j URI must use one of the following schemes: "
                "neo4j, neo4j+s, neo4j+ssc, bolt, bolt+s, bolt+ssc."
            )
        if not parsed.netloc:
            raise ValueError("The Neo4j URI must include a host.")
        return v

    @property
    def uri_safe(self) -> str:
        try:
            parsed = urlparse(self.uri)
            host = parsed.hostname or ""
            port = parsed.port
            host_port = f"{host}:{port}" if port else host
            return f"{parsed.scheme}://{host_port}"
        except Exception:
            return "<redacted-neo4j-uri>"
