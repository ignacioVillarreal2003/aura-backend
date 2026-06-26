from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator

_MAX_ID = 2_147_483_647
_MAX_CHARS_PER_QUERY = 16_000
_MAX_FRAGMENTS_PER_QUERY_STRATEGY = 50
_MAX_TOTAL_FRAGMENTS = 100
_MAX_QUERIES_PER_TYPE = 10


class _BaseQuery(BaseModel):
    text: str
    max_fragments: int = Field(..., ge=1, le=_MAX_FRAGMENTS_PER_QUERY_STRATEGY)

    @field_validator("text")
    @classmethod
    def clean_text(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("text must not be blank.")
        return v

    model_config = {"frozen": True}


class SemanticQuery(_BaseQuery):
    text: str = Field(..., min_length=1, max_length=_MAX_CHARS_PER_QUERY)


class BM25Query(_BaseQuery):
    text: str = Field(..., min_length=1, max_length=_MAX_CHARS_PER_QUERY)


class RerankConfig(BaseModel):
    enabled: bool = False
    max_fragments: Optional[int] = Field(default=None, ge=1, le=_MAX_TOTAL_FRAGMENTS)

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
    chat_id: Optional[int] = Field(default=None, gt=0, le=_MAX_ID)

    semantic_queries: list[SemanticQuery] = Field(
        default_factory=list,
        max_length=_MAX_QUERIES_PER_TYPE,
    )
    bm25_queries: list[BM25Query] = Field(
        default_factory=list,
        max_length=_MAX_QUERIES_PER_TYPE,
    )

    rerank: RerankConfig = Field(default_factory=RerankConfig)
    adjacent_chunks: int = Field(default=0, ge=0, le=3)
    context_expansion: Literal["none", "adjacent", "section"] = "adjacent"

    @model_validator(mode="after")
    def _validate_queries(self) -> "QuestionContextFragmentsRequest":
        total_sources = len(self.semantic_queries) + len(self.bm25_queries)

        if total_sources == 0:
            raise ValueError("At least one query must be provided.")

        if self.rerank.enabled:
            pool = (
                    sum(q.max_fragments for q in self.semantic_queries)
                    + sum(q.max_fragments for q in self.bm25_queries)
            )

            if self.rerank.max_fragments is not None and self.rerank.max_fragments > pool:
                raise ValueError(
                    f"rerank.max_fragments ({self.rerank.max_fragments}) "
                    f"cannot exceed total retrieved fragments ({pool})."
                )

        return self

    model_config = {"frozen": True}
