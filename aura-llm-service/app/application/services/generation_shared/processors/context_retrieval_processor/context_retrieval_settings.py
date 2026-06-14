from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ContextRetrievalSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CONTEXT_RETRIEVAL_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    semantic_fragments_per_lane: int = Field(default=3, ge=1, le=50)
    bm25_fragments_per_lane: int = Field(default=3, ge=1, le=50)
    use_rerank: bool = Field(default=True)
    max_fragments: int = Field(default=12, ge=1, le=100)
    adjacent_chunks: int = Field(default=1, ge=0, le=3)
