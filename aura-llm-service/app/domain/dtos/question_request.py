from typing import List, Optional
from pydantic import BaseModel, Field

from app.domain.dtos.question import Question


class QuestionRequest(BaseModel):
    question: str = Field(...)
    context: Optional[str] = None
    messages: Optional[List[Question]] = None
    stream: bool = False