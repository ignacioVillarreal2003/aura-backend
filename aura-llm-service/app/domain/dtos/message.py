from pydantic import BaseModel, Field, model_validator

from app.domain.constants.message_role import MessageRole
from app.domain.field_limits import MAX_MESSAGE_CONTENT_CHARS


class Message(BaseModel):
    role: MessageRole = Field(...)
    content: str = Field(..., min_length=1, max_length=MAX_MESSAGE_CONTENT_CHARS)

    @model_validator(mode="after")
    def validate_message(self) -> "Message":
        content = self.content.strip()
        if not content:
            raise ValueError("Message content must not be blank.")
        if content != self.content:
            return self.model_copy(update={"content": content})
        return self

    model_config = {"frozen": True}
