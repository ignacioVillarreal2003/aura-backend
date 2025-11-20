from pydantic import BaseModel, Field


class QuestionResponse(BaseModel):
    answer: str = Field(...)