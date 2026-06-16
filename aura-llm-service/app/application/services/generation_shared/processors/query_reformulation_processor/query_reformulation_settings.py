from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class QueryReformulationSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="QUERY_REFORMULATION_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    history_messages_window: int = Field(default=4, ge=0, le=20)
    rewrite_query: bool = Field(default=True)
    use_keywords: bool = Field(default=True)
    max_rewrite_tokens: int = Field(default=500, ge=1, le=8192)
    max_keywords_tokens: int = Field(default=500, ge=1, le=8192)
    temperature: Optional[float] = Field(default=0.0, ge=0.0, le=2.0)
