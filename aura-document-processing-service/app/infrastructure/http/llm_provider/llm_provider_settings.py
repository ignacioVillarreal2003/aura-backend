from typing import Optional
from urllib.parse import urlparse
from pydantic import Field, field_validator, model_validator
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
    classify_timeout_seconds: Optional[float] = Field(default=None, gt=0, le=600.0)
    enrich_timeout_seconds: Optional[float] = Field(default=None, gt=0, le=600.0)

    max_document_name_length: int = Field(default=512, ge=1, le=2048)
    max_classify_content_length: int = Field(default=5_000_000, ge=1024, le=50_000_000)
    max_enrich_content_length: int = Field(default=1_000_000, ge=256, le=10_000_000)

    allowed_llm_hosts: Optional[str] = Field(
        default=None,
        description="Optional comma-separated list of allowed hostnames for LLM URLs (no scheme/port).",
    )

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

    @model_validator(mode="after")
    def validate_urls_have_host_and_allowlist(
            self
    ) -> "LlmProviderSettings":
        for name in ("classify_document_url", "enrich_fragment_url"):
            url = getattr(self, name)
            parsed = urlparse(url)
            if not parsed.netloc:
                raise ValueError(f"{name} must include a valid host.")

        if self.allowed_llm_hosts:
            allowed = {
                h.strip().lower()
                for h in self.allowed_llm_hosts.split(",")
                if h.strip()
            }
            if not allowed:
                return self
            for name in ("classify_document_url", "enrich_fragment_url"):
                url = getattr(self, name)
                host = (urlparse(url).hostname or "").lower()
                if host not in allowed:
                    raise ValueError(
                        f"The host of {name} is not in LLM_PROVIDER_ALLOWED_LLM_HOSTS."
                    )

        return self

    def effective_classify_timeout_seconds(self) -> float:
        return float(self.classify_timeout_seconds or self.timeout_seconds)

    def effective_enrich_timeout_seconds(self) -> float:
        return float(self.enrich_timeout_seconds or self.timeout_seconds)
