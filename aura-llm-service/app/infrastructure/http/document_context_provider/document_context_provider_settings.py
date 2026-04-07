import logging
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


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

    max_chars_per_fragment: int = Field(default=10_000, ge=1_000, le=100_000)
    truncate_oversized_fragments: bool = Field(default=False)
    max_total_chars: int = Field(default=100_000, ge=10_000, le=1_000_000)
    max_question_chars: int = Field(default=16_000, ge=256, le=500_000)
    max_fragments_cap: int = Field(default=50, ge=1, le=500)
    max_document_ids_per_request: int = Field(default=50, ge=1, le=500)

    @field_validator(
        "question_context_fragments_url",
        "document_context_fragments_url",
        mode="before"
    )
    @classmethod
    def validate_url(
            cls,
            v: str
    ) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("URL must be a non-empty string.")
        v = v.strip().rstrip("/")
        if not v.startswith(("http://", "https://")):
            raise ValueError(f"URL must start with http:// or https://, got: '{v}'.")
        return v

    @model_validator(
        mode="after"
    )
    def validate_limits_coherence(
            self
    ) -> "DocumentContextProviderSettings":
        if self.max_chars_per_fragment > self.max_total_chars:
            raise ValueError(
                f"max_chars_per_fragment ({self.max_chars_per_fragment:,}) cannot exceed "
                f"max_total_chars ({self.max_total_chars:,}). "
                "A single fragment would exhaust the entire character budget."
            )
        return self