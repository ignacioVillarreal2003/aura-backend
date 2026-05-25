from typing import Optional
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
    max_fragments: Optional[int] = Field(default=None, ge=1, le=MAX_TOTAL_FRAGMENTS)

    @model_validator(mode="after")
    def validate_rerank_consistency(self) -> "RerankConfig":
        if self.enabled and self.max_fragments is None:
            raise ValueError("rerank.max_fragments is required when rerank is enabled.")
        if not self.enabled and self.max_fragments is not None:
            raise ValueError(
                "rerank.max_fragments has no effect when rerank is disabled."
            )
        return self

    model_config = {"frozen": True}


class QuestionContextFragmentsRequest(BaseModel):
    chat_id: Optional[ChatId] = Field(default=None, gt=0, le=MAX_ID)

    semantic_queries: list[_SemanticQuery] = Field(
        default_factory=list,
        max_length=MAX_QUERIES_PER_TYPE,
    )
    bm25_queries: list[_BM25Query] = Field(
        default_factory=list,
        max_length=MAX_QUERIES_PER_TYPE,
    )

    rerank: _RerankConfig = Field(default_factory=_RerankConfig)

    adjacent_chunks: int = Field(default=0, ge=0, le=3)

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

            if self.rerank.max_fragments > pool:
                raise ValueError(
                    f"rerank.max_fragments ({self.rerank.max_fragments}) "
                    f"cannot exceed total retrieved fragments ({pool})."
                )

        return self

    model_config = {"frozen": True}
