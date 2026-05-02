from typing import Optional
from pydantic import BaseModel, Field, model_validator

from app.domain.field_limits import (
    MAX_ID,
    MAX_KEYWORDS_CHARS,
    MAX_QUESTION_CHARS,
    MAX_FRAGMENTS_PER_QUERY_STRATEGY,
    MAX_RERANK_FRAGMENTS,
)
from app.domain.types import ChatId


class QuestionContextFragmentsRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=MAX_QUESTION_CHARS)
    question_max_fragments: int = Field(..., ge=1, le=MAX_FRAGMENTS_PER_QUERY_STRATEGY)
    chat_id: Optional[ChatId] = Field(default=None, gt=0, le=MAX_ID)
    use_keywords: Optional[bool] = Field(default=None)
    keywords: Optional[str] = Field(default=None, min_length=1, max_length=MAX_KEYWORDS_CHARS)
    keywords_max_fragments: Optional[int] = Field(
        default=None, ge=1, le=MAX_FRAGMENTS_PER_QUERY_STRATEGY
    )
    use_rerank: Optional[bool] = Field(default=None)
    rerank_max_fragments: Optional[int] = Field(
        default=None, ge=1, le=MAX_RERANK_FRAGMENTS
    )
    use_bm25: Optional[bool] = Field(default=None)
    bm25_max_fragments: Optional[int] = Field(
        default=None, ge=1, le=MAX_FRAGMENTS_PER_QUERY_STRATEGY
    )

    @model_validator(mode="after")
    def validate_request(self) -> "QuestionContextFragmentsRequest":
        base = self
        question = base.question.strip()
        if not question:
            raise ValueError("question must not be blank.")

        keywords = base.keywords
        if keywords is not None:
            k = keywords.strip()
            keywords = k or None

        if base.use_keywords:
            if not keywords:
                raise ValueError("keywords must be provided when use_keywords is true.")
            if base.keywords_max_fragments is None:
                raise ValueError("keywords_max_fragments must be provided when use_keywords is true.")

        if base.use_bm25:
            if base.bm25_max_fragments is None:
                raise ValueError("bm25_max_fragments must be provided when use_bm25 is true.")
        if not base.use_bm25 and base.bm25_max_fragments is not None:
            raise ValueError("bm25_max_fragments may only be set when use_bm25 is true.")

        if not base.use_rerank and base.rerank_max_fragments is not None:
            raise ValueError("rerank_max_fragments may only be set when use_rerank is true.")

        if base.use_rerank:
            if base.rerank_max_fragments is None:
                raise ValueError("rerank_max_fragments must be provided when use_rerank is true.")
            max_rerank = base.question_max_fragments
            if base.use_keywords and base.keywords_max_fragments:
                max_rerank += base.keywords_max_fragments
            if base.use_bm25 and base.bm25_max_fragments:
                max_rerank += base.bm25_max_fragments
            if base.rerank_max_fragments > max_rerank:
                raise ValueError(
                    "rerank_max_fragments must not exceed the combined pool from question, "
                    "keywords, and bm25 retrievers."
                )

        if question != base.question or keywords != base.keywords:
            return base.model_copy(update={"question": question, "keywords": keywords})
        return base

    model_config = {"frozen": True}
