from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class FragmentQueryServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FRAGMENT_QUERY_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    similarity_threshold: float = Field(default=0.3, ge=0.0, le=1.0)

    contextual_retrieval_enabled: bool = Field(default=True)

    respect_section_boundaries: bool = Field(default=True)

    max_section_fragments: int = Field(default=12, ge=1, le=200)

    bm25_rrf_k: int = Field(default=60, ge=1, le=10_000)
    bm25_min_score: float = Field(default=0.0)
    bm25_query_max_chars: int = Field(default=512, ge=1, le=4_000)

    max_retrieval_concurrency: int = Field(default=8, ge=1, le=64)

    rerank_candidate_pool_cap: int = Field(default=200, ge=1, le=1_000)
