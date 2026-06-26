from typing import Optional
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class GraphContextProviderSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GRAPH_CONTEXT_PROVIDER_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    enabled: bool = Field(default=True)
    url: Optional[str] = Field(default=None)
    query_url: Optional[str] = Field(default=None)
    timeout_seconds: float = Field(default=15.0, gt=0, le=120)

    retry_max_attempts: int = Field(default=3, ge=1, le=10)
    retry_backoff_min_seconds: float = Field(default=0.5, gt=0, le=30.0)
    retry_backoff_max_seconds: float = Field(default=5.0, gt=0, le=60.0)

    @field_validator("url", "query_url", mode="before")
    @classmethod
    def _validate_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = str(v).strip().rstrip("/")
        if not v:
            return None
        if not v.startswith(("http://", "https://")):
            raise ValueError(f"url must start with http:// or https://, got: '{v}'.")
        return v

    @model_validator(mode="after")
    def _validate_backoff(self) -> "GraphContextProviderSettings":
        if self.retry_backoff_min_seconds >= self.retry_backoff_max_seconds:
            raise ValueError("retry_backoff_min_seconds must be less than retry_backoff_max_seconds.")
        return self

    @property
    def is_active(self) -> bool:
        return self.enabled and bool(self.url)

    @property
    def resolve_query_url(self) -> Optional[str]:
        if self.query_url:
            return self.query_url
        if not self.url:
            return None
        if self.url.endswith("/context"):
            return f"{self.url[: -len('/context')]}/query"
        return f"{self.url}/query"
