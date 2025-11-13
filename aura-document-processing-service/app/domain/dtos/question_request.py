from fastapi import Form
from pydantic import BaseModel, Field


class QuestionRequest(BaseModel):
    question: str = Field(...)