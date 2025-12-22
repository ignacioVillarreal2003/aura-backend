from pydantic import BaseModel, Field

from app.domain.constants.message_role import MessageRole


class Message(BaseModel):
    role: MessageRole = Field(...)
    content: str = Field(...)
