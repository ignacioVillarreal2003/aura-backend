from pydantic import BaseModel, Field, model_validator

from app.domain.constants.message_role import MessageRole
from app.domain.dtos.message import Message
from app.domain.field_limits import MAX_ID, MAX_INSTRUCTION_CHARS, MAX_MESSAGES_IN_REQUEST


class AgentRequest(BaseModel):
    messages: list[Message] = Field(..., min_length=1, max_length=MAX_MESSAGES_IN_REQUEST)
    chat_id: int = Field(..., gt=0, le=MAX_ID)
    system_prompt: str | None = Field(
        default=None,
        min_length=1,
        max_length=MAX_INSTRUCTION_CHARS,
        description="Instrucción de sistema personalizada del operador.",
    )
    response_style: str | None = Field(
        default=None,
        min_length=1,
        max_length=MAX_INSTRUCTION_CHARS,
        description="Estilo de respuesta esperado por el operador.",
    )

    @model_validator(mode="after")
    def validate_request(self) -> "AgentRequest":
        if self.messages[-1].role != MessageRole.human:
            raise ValueError("The last message must be from the human role.")
        return self

    model_config = {"frozen": True}
