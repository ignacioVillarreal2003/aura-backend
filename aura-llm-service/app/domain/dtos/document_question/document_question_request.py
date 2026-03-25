from pydantic import BaseModel, Field

from app.domain.dtos.message import Message


class DocumentQuestionRequest(BaseModel):
    messages: list[Message] = Field(...)
