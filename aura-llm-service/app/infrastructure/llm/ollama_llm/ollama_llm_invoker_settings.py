from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class OllamaLLMInvokerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OLLAMA_LLM_INVOKER_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    max_retry_attempts: int = Field(default=3, ge=1, le=10)
    retry_min_wait: float = Field(default=1.0, ge=0.1, le=60.0)
    retry_max_wait: float = Field(default=8.0, ge=1.0, le=300.0)
    max_stream_response_chars: int = Field(default=100_000, ge=1_000, le=10_000_000)

    log_payloads: bool = Field(default=False)
    log_payload_max_chars: int = Field(default=2_000, ge=100, le=50_000)
