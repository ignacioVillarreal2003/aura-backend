from typing import Optional

from pydantic import BaseModel, Field


class QuestionContextFragmentsRequest(BaseModel):
    question: str = Field(...)
    max_fragments: int = Field(...)
    search_keywords: Optional[str] = Field(
        default=None,
        description="Optional shortened query text used only for vector embedding and similarity search.",
    )
    use_rerank: Optional[bool] = Field(
        default=None,
        description="When true and reranking is enabled in service settings, rerank retrieved fragments.",
    )
    rerank_final_fragments: Optional[int] = Field(
        default=None,
        description="Number of fragments to keep after reranking; must not exceed max_fragments when set.",
    )
