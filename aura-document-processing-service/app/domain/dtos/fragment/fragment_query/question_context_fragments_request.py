from typing import Optional

from pydantic import BaseModel, Field


class QuestionContextFragmentsRequest(BaseModel):
    question: str = Field(...)
    max_fragments: int = Field(...)
    search_keywords: Optional[str] = Field(default=None)
    use_rerank: Optional[bool] = Field(default=None)
    rerank_final_fragments: Optional[int] = Field(default=None)
