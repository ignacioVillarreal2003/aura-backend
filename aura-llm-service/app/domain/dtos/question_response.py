from pydantic import BaseModel, Field


class QuestionResponse(BaseModel):
    question: str = Field(...)
    response: str = Field(...)