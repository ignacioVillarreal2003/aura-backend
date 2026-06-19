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

    similarity_threshold: float = Field(default=0.5, ge=0.0, le=1.0)

    # When True, adjacency expansion stays within the seed fragment's structural
    # section: a neighbor is only pulled in if it shares the seed's section_path.
    # Fragments without a section_path (flat-text fallback splitters) are unaffected
    # and keep pure fragment_index contiguity. Prevents bleeding context across
    # section/page boundaries for Docling-chunked documents.
    respect_section_boundaries: bool = Field(default=True)

    bm25_rrf_k: int = Field(default=60, ge=1, le=10_000)
    bm25_min_score: float = Field(default=0.0)
    bm25_query_max_chars: int = Field(default=512, ge=1, le=4_000)

    # Upper bound on concurrent retrieval queries per request. Each parallel
    # vector/BM25 query runs on its own database session (an AsyncSession is not
    # safe for concurrent use), so this caps how many pooled connections a single
    # request can hold at once. Keep it well under the connection pool size.
    max_retrieval_concurrency: int = Field(default=8, ge=1, le=64)

    # Defensive ceiling on how many fused candidates the cross-encoder scores.
    # The reranker runs one forward pass per candidate (O(pool)), and the fused
    # pool can reach MAX_QUERIES_PER_TYPE * MAX_FRAGMENTS_PER_QUERY_STRATEGY
    # (~1000) candidates. Since the fused list is already ordered by RRF score,
    # truncating to this cap keeps the strongest candidates while bounding
    # reranker latency. Only the candidate count is capped; rerank.max_fragments
    # still governs how many results are returned.
    rerank_candidate_pool_cap: int = Field(default=200, ge=1, le=1_000)
