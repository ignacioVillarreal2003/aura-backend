from pydantic import Field, field_validator
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
    timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    max_fragments_per_document_response: int = Field(default=100, ge=1, le=500)

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

