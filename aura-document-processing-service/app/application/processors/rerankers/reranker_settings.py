import logging
from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.application.processors.rerankers.constants.reranker_type import RerankerType

logger = logging.getLogger(__name__)


class RerankerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RERANKER_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    active_type: RerankerType = Field(default=RerankerType.cross_encoder)

    model_name: str = Field(default="BAAI/bge-reranker-v2-m3")
    device: Optional[str] = Field(default=None)
    min_score: float = Field(default=0.35, ge=0.0, le=1.0)
    min_score_fallback_to_topk: bool = Field(default=True)
    batch_size: int = Field(default=64, ge=1, le=512)
    max_length: int = Field(default=1024, ge=64, le=8192)

    @field_validator("device", mode="before")
    @classmethod
    def normalize_device(cls, value: Optional[str]) -> Optional[str]:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        return value.strip().lower()
