from typing import Optional
from pydantic import BaseModel, Field

from app.domain.dtos.message import Message


class QuestionRequest(BaseModel):
    question: str = Field(...)
    context: Optional[str] = None
    messages: Optional[list[Message]] = None