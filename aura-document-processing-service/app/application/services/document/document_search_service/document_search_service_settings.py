from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DocumentSearchServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DOCUMENT_SEARCH_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    similarity_threshold: float = Field(default=0.3, ge=0.0, le=1.0)
    candidate_pool_size: int = Field(default=200, ge=1, le=5_000)

    bm25_min_score: float = Field(default=0.0, ge=0.0)
    bm25_query_max_chars: int = Field(default=512, ge=1, le=4_000)
    bm25_relevance_saturation: float = Field(default=10.0, gt=0.0)

    rerank_enabled: bool = Field(default=True)
    rerank_candidate_pool: int = Field(default=80, ge=1, le=400)
