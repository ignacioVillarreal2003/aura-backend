from pydantic import BaseModel, Field


class ContextFragmentsByQuestionRequest(BaseModel):
    question: str = Field(...)
    max_context_fragments_count: int = Field(...)
