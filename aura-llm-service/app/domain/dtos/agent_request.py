from typing import Optional
from pydantic import BaseModel, Field

from app.domain.dtos.message import Message


class AgentRequest(BaseModel):
    message: str = Field(...)
    history_messages: Optional[list[Message]] = None
