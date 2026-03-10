from typing import List
from pydantic import BaseModel, Field

from app.domain.dtos.message import Message


class AgentRequest(BaseModel):
    messages: List[Message] = Field(
        ...
    )
