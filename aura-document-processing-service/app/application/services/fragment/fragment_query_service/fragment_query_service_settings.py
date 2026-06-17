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

    similarity_threshold: float = Field(default=0.65, ge=0.0, le=1.0)

    bm25_rrf_k: int = Field(default=60, ge=1, le=10_000)
    bm25_min_score: float = Field(default=0.0)
    bm25_query_max_chars: int = Field(default=512, ge=1, le=4_000)

    # Upper bound on concurrent retrieval queries per request. Each parallel
    # vector/BM25 query runs on its own database session (an AsyncSession is not
    # safe for concurrent use), so this caps how many pooled connections a single
    # request can hold at once. Keep it well under the connection pool size.
    max_retrieval_concurrency: int = Field(default=8, ge=1, le=64)
