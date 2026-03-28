from pydantic import BaseModel, Field


class QuestionContextFragmentsRequest(BaseModel):
    question: str = Field(...)
    max_fragments: int = Field(...)