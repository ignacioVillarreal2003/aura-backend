from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LlmProviderSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LLM_PROVIDER_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    classify_document_url: str = Field(...)
    enrich_fragment_url: str = Field(...)
    timeout_seconds: float = Field(default=120.0, gt=0, le=600.0)

    @field_validator(
        "classify_document_url",
        "enrich_fragment_url",
        mode="before"
    )
    @classmethod
    def validate_http_url(
            cls,
            v: str
    ) -> str:
        v = v.strip().rstrip("/")
        if not v.startswith(("http://", "https://")):
            raise ValueError("Each LLM URL must start with http:// or https://.")
        return v
