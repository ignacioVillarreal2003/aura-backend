from typing import Optional

from pydantic import BaseModel, Field, model_validator

from app.domain.constants.message_role import MessageRole
from app.domain.dtos.message import Message
from app.domain.field_limits import MAX_HISTORY_MESSAGES, MAX_INSTRUCTION_CHARS, MAX_MESSAGES_IN_REQUEST


class GeneralChatRequest(BaseModel):
    messages: list[Message] = Field(..., min_length=1, max_length=MAX_MESSAGES_IN_REQUEST)
    system_prompt: Optional[str] = Field(default=None, min_length=1, max_length=MAX_INSTRUCTION_CHARS)

    @model_validator(mode="after")
    def validate_request(self) -> "GeneralChatRequest":
        if self.messages[-1].role != MessageRole.human:
            raise ValueError("The last message must be from the human role.")
        history_count = len(self.messages) - 1
        if history_count > MAX_HISTORY_MESSAGES:
            raise ValueError(
                f"Message history must not exceed {MAX_HISTORY_MESSAGES} messages."
            )
        if self.system_prompt is not None:
            stripped = self.system_prompt.strip()
            if not stripped:
                raise ValueError("system_prompt must not be blank if provided.")
            if stripped != self.system_prompt:
                return self.model_copy(update={"system_prompt": stripped})
        return self

    model_config = {"frozen": True}
