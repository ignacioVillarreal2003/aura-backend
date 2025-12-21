from typing import Optional
from pydantic import BaseModel, Field

from app.domain.dtos.message import Message


class AgentRequest(BaseModel):
    message: str = Field(..., description="The user's message or question")
    messages: Optional[list[Message]] = Field(
        default=None,
        description="Optional conversation history"
    )
