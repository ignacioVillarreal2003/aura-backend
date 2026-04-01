from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RerankContextSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RERANK_CONTEXT_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    model_name: str = Field(default="BAAI/bge-reranker-v2-m3")
    device: Optional[str] = Field(default=None)

    threshold: int = Field(default=6, ge=1, le=50)
    top_n: int = Field(default=6, ge=1, le=50)
    min_score: float = Field(default=-10.0)
    batch_size: int = Field(default=16, ge=1, le=512)

    @field_validator("device", mode="before")
    @classmethod
    def normalize_device(cls, v: Optional[str]) -> Optional[str]:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return v.strip().lower()
