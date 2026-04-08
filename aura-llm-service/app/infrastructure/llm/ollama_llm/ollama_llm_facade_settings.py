import logging
from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class OllamaLLMFacadeSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OLLAMA_LLM_FACADE_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    model_name: str = Field(...)
    base_url: str = Field(...)

    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    top_k: Optional[int] = Field(default=None, ge=1, le=500)

    num_ctx: Optional[int] = Field(default=None, ge=512, le=131_072)
    num_predict: Optional[int] = Field(default=None, ge=1, le=32_768)

    request_timeout: Optional[float] = Field(default=120.0, gt=0, le=600.0)

    @field_validator("model_name", mode="before")
    @classmethod
    def validate_model_name(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("model_name must be a non-empty string")
        return v.strip()

    @field_validator("base_url", mode="before")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("base_url must be a non-empty string")
        v = v.strip().rstrip("/")
        if not v.startswith(("http://", "https://")):
            raise ValueError(f"base_url must start with http:// or https://, got: '{v}'")
        return v

    def get_chat_ollama_kwargs(self) -> dict:
        kwargs: dict = {
            "model": self.model_name,
            "base_url": self.base_url,
            "temperature": self.temperature
        }

        if self.top_p is not None:
            kwargs["top_p"] = self.top_p
        if self.top_k is not None:
            kwargs["top_k"] = self.top_k
        if self.num_ctx is not None:
            kwargs["num_ctx"] = self.num_ctx
        if self.num_predict is not None:
            kwargs["num_predict"] = self.num_predict
        if self.request_timeout is not None:
            kwargs["timeout"] = self.request_timeout

        return kwargs
