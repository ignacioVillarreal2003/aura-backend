from typing import Optional

from pydantic import BaseModel, Field, model_validator

from app.domain.constants.message_role import MessageRole
from app.domain.dtos.message import Message
from app.domain.field_limits import MAX_HISTORY_MESSAGES, MAX_ID, MAX_MESSAGES_IN_REQUEST


class DocumentQuestionRequest(BaseModel):
    messages: list[Message] = Field(..., min_length=1, max_length=MAX_MESSAGES_IN_REQUEST)
    chat_id: Optional[int] = Field(default=None, gt=0, le=MAX_ID)

    @model_validator(mode="after")
    def validate_request(self) -> "DocumentQuestionRequest":
        if self.messages[-1].role != MessageRole.human:
            raise ValueError("The last message must be from the human role.")
        history_count = len(self.messages) - 1
        if history_count > MAX_HISTORY_MESSAGES:
            raise ValueError(
                f"Message history must not exceed {MAX_HISTORY_MESSAGES} messages."
            )
        return self

    model_config = {"frozen": True}
