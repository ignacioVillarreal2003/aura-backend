from typing import Optional
from urllib.parse import urlparse
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.domain.field_limits import (
    MAX_LLM_CLASSIFY_CONTENT_CHARS,
    MAX_LLM_CONTEXTUALIZE_CONTENT_CHARS,
    MAX_LLM_DOCUMENT_NAME_CHARS,
    MAX_LLM_EXTRACT_CONTENT_CHARS,
)


class LlmProviderSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LLM_PROVIDER_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    classify_document_url: str = Field(...)
    contextualize_fragment_url: str = Field(...)
    extract_entities_relations_url: Optional[str] = Field(
        default=None,
        description=(
            "Optional URL of the LLM service endpoint that extracts "
            "entities and relations from a fragment. Required only when "
            "the knowledge graph module is enabled."
        ),
    )
    translate_graph_query_url: Optional[str] = Field(
        default=None,
        description=(
            "Optional URL of the LLM service endpoint that translates a "
            "natural-language question into a structured graph intent. "
            "Required only when the knowledge graph module is enabled."
        ),
    )

    timeout_seconds: float = Field(default=120.0, gt=0, le=3600.0)
    classify_timeout_seconds: Optional[float] = Field(default=None, gt=0, le=3600.0)
    contextualize_timeout_seconds: Optional[float] = Field(default=None, gt=0, le=3600.0)
    extract_entities_relations_timeout_seconds: float = Field(
        default=900.0,
        gt=0,
        le=3600.0,
        description=(
            "HTTP read timeout for graph extraction calls. Ollama/GPU runs often "
            "exceed the general LLM_PROVIDER_TIMEOUT_SECONDS default."
        ),
    )
    translate_graph_query_timeout_seconds: Optional[float] = Field(
        default=None, gt=0, le=3600.0
    )

    max_document_name_length: int = Field(default=MAX_LLM_DOCUMENT_NAME_CHARS, ge=1, le=MAX_LLM_DOCUMENT_NAME_CHARS)
    max_classify_content_length: int = Field(default=MAX_LLM_CLASSIFY_CONTENT_CHARS, ge=1024, le=MAX_LLM_CLASSIFY_CONTENT_CHARS)
    max_contextualize_content_length: int = Field(default=MAX_LLM_CONTEXTUALIZE_CONTENT_CHARS, ge=256, le=MAX_LLM_CONTEXTUALIZE_CONTENT_CHARS)
    max_extract_content_length: int = Field(default=MAX_LLM_EXTRACT_CONTENT_CHARS, ge=256, le=MAX_LLM_EXTRACT_CONTENT_CHARS)
    max_translate_query_question_length: int = Field(default=4_000, ge=64, le=64_000)

    allowed_llm_hosts: Optional[str] = Field(
        default=None,
        description="Optional comma-separated list of allowed hostnames for LLM URLs (no scheme/port).",
    )

    @field_validator(
        "classify_document_url",
        "contextualize_fragment_url",
        "extract_entities_relations_url",
        "translate_graph_query_url",
        mode="before",
    )
    @classmethod
    def validate_http_url(
            cls,
            v: Optional[str],
    ) -> Optional[str]:
        if v is None:
            return None
        v = str(v).strip().rstrip("/")
        if not v:
            return None
        if not v.startswith(("http://", "https://")):
            raise ValueError("Each LLM URL must start with http:// or https://.")
        return v

    @model_validator(mode="after")
    def validate_urls_have_host_and_allowlist(
            self
    ) -> "LlmProviderSettings":
        required_urls = ("classify_document_url", "contextualize_fragment_url")
        optional_urls = ("extract_entities_relations_url", "translate_graph_query_url")

        for name in required_urls:
            url = getattr(self, name)
            parsed = urlparse(url)
            if not parsed.netloc:
                raise ValueError(f"{name} must include a valid host.")

        for name in optional_urls:
            url = getattr(self, name)
            if url is None:
                continue
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
            for name in required_urls + optional_urls:
                url = getattr(self, name)
                if url is None:
                    continue
                host = (urlparse(url).hostname or "").lower()
                if host not in allowed:
                    raise ValueError(
                        f"The host of {name} is not in LLM_PROVIDER_ALLOWED_LLM_HOSTS."
                    )

        return self

    def effective_classify_timeout_seconds(self) -> float:
        return float(self.classify_timeout_seconds or self.timeout_seconds)

    def effective_contextualize_timeout_seconds(self) -> float:
        return float(self.contextualize_timeout_seconds or self.timeout_seconds)

    def effective_extract_entities_relations_timeout_seconds(self) -> float:
        return self.extract_entities_relations_timeout_seconds

    def effective_translate_graph_query_timeout_seconds(self) -> float:
        return float(
            self.translate_graph_query_timeout_seconds or self.timeout_seconds
        )
