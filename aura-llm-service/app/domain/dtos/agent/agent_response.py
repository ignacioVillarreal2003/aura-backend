from pydantic import BaseModel, Field

from app.domain.dtos.message import Message
from app.domain.field_limits import MAX_MESSAGES_IN_REQUEST


class AgentResponse(BaseModel):
    messages: list[Message] = Field(..., min_length=1, max_length=MAX_MESSAGES_IN_REQUEST)

    model_config = {
        "from_attributes": True
    }
