import re
from pydantic import BaseModel, Field, field_validator

from app.domain.constants.message_role import MessageRole
from app.domain.field_limits import MAX_MESSAGE_CONTENT_CHARS

_CONTROL_CHARS_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


class Message(BaseModel):
    role: MessageRole = Field(...)
    content: str = Field(..., min_length=1, max_length=MAX_MESSAGE_CONTENT_CHARS)

    @field_validator("content", mode="after")
    @classmethod
    def sanitize_content(cls, value: str) -> str:
        content = _CONTROL_CHARS_PATTERN.sub("", value).strip()
        if not content:
            raise ValueError("Message content must not be blank.")
        return content

    model_config = {"frozen": True}
