from pydantic import BaseModel, Field, model_validator

from app.domain.dtos.message import Message
from app.domain.field_limits import MAX_CONTENT_CHARS, MAX_MESSAGES_IN_REQUEST


class GeneralChatResponse(BaseModel):
    answer: str = Field(..., min_length=1, max_length=MAX_CONTENT_CHARS)
    messages: list[Message] = Field(..., min_length=1, max_length=MAX_MESSAGES_IN_REQUEST)

    @model_validator(mode="after")
    def validate_response(self) -> "GeneralChatResponse":
        answer = self.answer.strip()
        if not answer:
            raise ValueError("Answer must not be blank.")
        if answer != self.answer:
            return self.model_copy(update={"answer": answer})
        return self

    model_config = {"from_attributes": True}
