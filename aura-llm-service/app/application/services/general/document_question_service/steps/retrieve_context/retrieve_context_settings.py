from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RetrieveContextSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RETRIEVE_CONTEXT_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    max_fragments: int = Field(default=3, ge=1, le=50)
    use_rerank: bool = Field(default=False)
    rerank_final_fragments: Optional[int] = Field(default=None)
    send_search_keywords: bool = Field(default=True)

    @model_validator(mode="after")
    def validate_rerank_coherence(self) -> "RetrieveContextSettings":
        if self.rerank_final_fragments is not None and not self.use_rerank:
            raise ValueError("rerank_final_fragments requires use_rerank to be true.")
        if self.rerank_final_fragments is not None and self.rerank_final_fragments > self.max_fragments:
            raise ValueError("rerank_final_fragments must not exceed max_fragments.")
        if self.rerank_final_fragments is not None and self.rerank_final_fragments < 1:
            raise ValueError("rerank_final_fragments must be at least one when set.")
        return self
