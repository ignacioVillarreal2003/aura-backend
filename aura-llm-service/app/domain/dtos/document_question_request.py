from typing import Optional
from pydantic import BaseModel, Field

from app.domain.dtos.message import Message


class DocumentQuestionRequest(BaseModel):
    question: str = Field(
        ...
    )
    history_messages: Optional[list[Message]] = None
