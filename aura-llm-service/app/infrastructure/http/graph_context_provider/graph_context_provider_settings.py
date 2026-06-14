from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class GraphContextProviderSettings(BaseSettings):
    """Settings for the knowledge-graph context client.

    The provider is active only when ``enabled`` is true AND ``url`` points
    to the document-processing service's ``/graph/context`` endpoint. With
    no URL configured the RAG flow silently skips graph enrichment, so the
    service boots fine in deployments without Neo4j.
    """

    model_config = SettingsConfigDict(
        env_prefix="GRAPH_CONTEXT_PROVIDER_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    enabled: bool = Field(default=True)
    url: Optional[str] = Field(default=None)
    timeout_seconds: float = Field(default=10.0, gt=0, le=120)

    @field_validator("url", mode="before")
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

    @property
    def is_active(self) -> bool:
        return self.enabled and bool(self.url)
