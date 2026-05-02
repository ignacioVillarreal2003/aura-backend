from typing import Optional
from pydantic import BaseModel, Field, model_validator

from app.domain.dtos.graph.graph_field_limits import (
    MAX_QUERY_QUESTION_CHARS,
    MAX_QUERY_RESULTS,
)
from app.domain.field_limits import MAX_ID
from app.domain.types import ChatId


class GraphQueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=MAX_QUERY_QUESTION_CHARS)
    max_results: int = Field(default=20, ge=1, le=MAX_QUERY_RESULTS)
    chat_id: Optional[ChatId] = Field(default=None, gt=0, le=MAX_ID)

    model_config = {"frozen": True}

    @model_validator(mode="after")
    def validate_question(self) -> "GraphQueryRequest":
        question = self.question.strip()
        if not question:
            raise ValueError("question must not be blank.")
        if question != self.question:
            return self.model_copy(update={"question": question})
        return self
