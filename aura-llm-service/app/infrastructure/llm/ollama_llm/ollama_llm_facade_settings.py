import logging
from typing import Optional, Union
from pydantic import Field, field_validator, model_validator
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
    top_p: Optional[float] = Field(default=0.9, ge=0.0, le=1.0)
    top_k: Optional[int] = Field(default=40, ge=1, le=500)
    repeat_penalty: Optional[float] = Field(default=1.05, ge=0.0, le=2.0)
    seed: Optional[int] = Field(default=None, ge=0)

    num_ctx: int = Field(default=24_576, ge=512, le=131_072)
    num_predict: Optional[int] = Field(default=6_144, le=32_768)

    prompt_overhead_tokens: int = Field(default=2_048, ge=0, le=32_768)
    output_reserve_tokens: int = Field(default=1_024, ge=1, le=32_768)
    fail_on_insufficient_context: bool = Field(default=False)

    circuit_failure_threshold: int = Field(default=3, ge=1, le=20)
    circuit_recovery_cooldown_seconds: float = Field(default=30.0, gt=0, le=600.0)

    request_timeout: Optional[float] = Field(default=300.0, gt=0, le=3600.0)
    keep_alive: Optional[Union[int, str]] = Field(default="30m")

    @field_validator("model_name", mode="before")
    @classmethod
    def validate_model_name(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("model_name must be a non-empty string.")
        return v.strip()

    @field_validator("base_url", mode="before")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("base_url must be a non-empty string.")
        v = v.strip().rstrip("/")
        if not v.startswith(("http://", "https://")):
            raise ValueError(f"base_url must start with http:// or https://, got: '{v}'.")
        return v

    @field_validator("num_predict", mode="before")
    @classmethod
    def validate_num_predict(cls, v: Optional[str]) -> Optional[int]:
        if v is None:
            return v
        v_int = int(v)
        if v_int < -2:
            raise ValueError("num_predict must be >= -2 (-1=unlimited, -2=fill context, positive=max tokens).")
        return v_int

    @field_validator("keep_alive", mode="before")
    @classmethod
    def validate_keep_alive(cls, v: Optional[Union[int, str]]) -> Optional[Union[int, str]]:
        if v is None:
            return None
        if isinstance(v, int):
            return v
        v = str(v).strip()
        if not v:
            return None
        try:
            return int(v)
        except ValueError:
            return v

    def output_reserve(self) -> int:
        if self.num_predict is not None and self.num_predict > 0:
            return self.num_predict
        return self.output_reserve_tokens

    @model_validator(mode="after")
    def validate_window_fits_output(self) -> "OllamaLLMFacadeSettings":
        reserve = self.output_reserve()
        if self.num_ctx <= reserve:
            raise ValueError(
                f"num_ctx ({self.num_ctx}) must be greater than the output reserve "
                f"({reserve} tokens); the prompt would have no room left."
            )
        return self

    def get_chat_ollama_kwargs(self) -> dict:
        kwargs: dict = {
            "model": self.model_name,
            "base_url": self.base_url,
            "temperature": self.temperature,
        }

        if self.top_p is not None:
            kwargs["top_p"] = self.top_p
        if self.top_k is not None:
            kwargs["top_k"] = self.top_k
        if self.repeat_penalty is not None:
            kwargs["repeat_penalty"] = self.repeat_penalty
        if self.seed is not None:
            kwargs["seed"] = self.seed
        if self.num_ctx is not None:
            kwargs["num_ctx"] = self.num_ctx
        if self.num_predict is not None:
            kwargs["num_predict"] = self.num_predict
        if self.request_timeout is not None:
            kwargs["timeout"] = self.request_timeout
        if self.keep_alive is not None:
            kwargs["keep_alive"] = self.keep_alive

        return kwargs
