from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DocumentContextProviderSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DOCUMENT_CONTEXT_PROVIDER_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    question_context_fragments_url: str = Field(...)
    document_context_fragments_url: str = Field(...)
    timeout_seconds: float = Field(default=120.0, gt=0, le=300)
    max_fragments_per_document_response: int = Field(default=100, ge=1, le=500)

    retry_max_attempts: int = Field(default=3, ge=1, le=10)
    retry_backoff_min_seconds: float = Field(default=0.5, gt=0, le=30.0)
    retry_backoff_max_seconds: float = Field(default=5.0, gt=0, le=60.0)

    log_payloads: bool = Field(default=False)
    log_payload_max_chars: int = Field(default=300, ge=50, le=10_000)

    @model_validator(mode="after")
    def _validate_backoff(self) -> "DocumentContextProviderSettings":
        if self.retry_backoff_min_seconds >= self.retry_backoff_max_seconds:
            raise ValueError("retry_backoff_min_seconds must be less than retry_backoff_max_seconds.")
        return self

    @field_validator(
        "question_context_fragments_url",
        "document_context_fragments_url",
        mode="before"
    )
    @classmethod
    def _validate_url(cls, v: str, info) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError(f"{info.field_name} must be a non-empty string.")
        v = v.strip().rstrip("/")
        if not v.startswith(("http://", "https://")):
            raise ValueError(f"{info.field_name} must start with http:// or https://, got: '{v}'.")
        return v
