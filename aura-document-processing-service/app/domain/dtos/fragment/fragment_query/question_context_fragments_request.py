from pydantic import BaseModel, Field, model_validator, field_validator

from app.domain.field_limits import (
    MAX_ID,
    MAX_CHARS_PER_QUERY,
    MAX_FRAGMENTS_PER_QUERY_STRATEGY,
    MAX_TOTAL_FRAGMENTS,
    MAX_QUERIES_PER_TYPE,
)
from app.domain.types import ChatId


class _BaseQuery(BaseModel):
    text: str
    max_fragments: int = Field(..., ge=1, le=MAX_FRAGMENTS_PER_QUERY_STRATEGY)

    @field_validator("text")
    @classmethod
    def clean_text(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("text must not be blank.")
        return v

    model_config = {"frozen": True}


class _SemanticQuery(_BaseQuery):
    text: str = Field(..., min_length=1, max_length=MAX_CHARS_PER_QUERY)


class _BM25Query(_BaseQuery):
    text: str = Field(..., min_length=1, max_length=MAX_CHARS_PER_QUERY)


class _RerankConfig(BaseModel):
    enabled: bool = False
    max_fragments: int | None = Field(default=None, ge=1, le=MAX_TOTAL_FRAGMENTS)

    @model_validator(mode="after")
    def validate_rerank_consistency(self) -> "_RerankConfig":
        if self.enabled and self.max_fragments is None:
            raise ValueError("rerank.max_fragments is required when rerank is enabled.")
        if not self.enabled and self.max_fragments is not None:
            raise ValueError(
                "rerank.max_fragments has no effect when rerank is disabled."
            )
        return self

    model_config = {"frozen": True}


class QuestionContextFragmentsRequest(BaseModel):
    chat_id: ChatId | None = Field(default=None, gt=0, le=MAX_ID)

    semantic_queries: list[_SemanticQuery] = Field(
        default_factory=list,
        max_length=MAX_QUERIES_PER_TYPE,
    )
    bm25_queries: list[_BM25Query] = Field(
        default_factory=list,
        max_length=MAX_QUERIES_PER_TYPE,
    )

    rerank: _RerankConfig = Field(default_factory=_RerankConfig)

    # Default to 1 so retrieval pulls each hit's immediate neighbours. This is the
    # query-time compensation for the structure-aware chunker's lack of overlap:
    # a concept split at a chunk border is recovered via its adjacent chunk (kept
    # within the same section by respect_section_boundaries). Set 0 to disable.
    adjacent_chunks: int = Field(default=1, ge=0, le=3)

    @model_validator(mode="after")
    def _validate_queries(self) -> "QuestionContextFragmentsRequest":
        total_sources = (
                len(self.semantic_queries)
                + len(self.bm25_queries)
        )

        if total_sources == 0:
            raise ValueError("At least one query must be provided.")

        if self.rerank.enabled:
            pool = (
                    sum(q.max_fragments for q in self.semantic_queries)
                    + sum(q.max_fragments for q in self.bm25_queries)
            )

            # `validate_rerank_consistency` on _RerankConfig guarantees max_fragments
            # is set whenever rerank is enabled; the None guard keeps mypy sound.
            rerank_max = self.rerank.max_fragments
            if rerank_max is not None and rerank_max > pool:
                raise ValueError(
                    f"rerank.max_fragments ({rerank_max}) "
                    f"cannot exceed total retrieved fragments ({pool})."
                )

        return self

    model_config = {"frozen": True}
