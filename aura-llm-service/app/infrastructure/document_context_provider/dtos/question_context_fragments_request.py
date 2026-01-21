from pydantic import BaseModel, Field


class QuestionContextFragmentsRequest(BaseModel):
    question: str = Field(...)
    max_context_fragments: int = Field(...)
