import logging
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class LlmProviderSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LLM_PROVIDER_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    base_url: str = Field(...)
    classify_document_path: str = Field(default="/api/document-classify")
    enrich_fragment_path: str = Field(default="/api/fragment-enrich")
    service_api_key: str = Field(...)
    timeout_seconds: float = Field(default=120.0)

    @field_validator("base_url", mode="before")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        v = v.strip().rstrip("/")
        if not v.startswith(("http://", "https://")):
            raise ValueError(
                f"base_url must start with http:// or https://, got: '{v}'"
            )
        return v

    @property
    def classify_document_url(self) -> str:
        return f"{self.base_url}{self.classify_document_path}"

    @property
    def enrich_fragment_url(self) -> str:
        return f"{self.base_url}{self.enrich_fragment_path}"
