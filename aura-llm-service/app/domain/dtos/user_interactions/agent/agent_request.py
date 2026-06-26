from pydantic import BaseModel, Field, model_validator

from app.domain.constants.message_role import MessageRole
from app.domain.dtos.message import Message
from app.domain.field_limits import MAX_ID, MAX_INSTRUCTION_CHARS, MAX_MESSAGES_IN_REQUEST
from app.domain.validation import OptionalPrompt


class AgentRequest(BaseModel):
    messages: list[Message] = Field(..., min_length=1, max_length=MAX_MESSAGES_IN_REQUEST)
    chat_id: int = Field(..., gt=0, le=MAX_ID)
    system_prompt: OptionalPrompt = Field(
        default=None,
        max_length=MAX_INSTRUCTION_CHARS,
        description="Instrucción de sistema personalizada del operador.",
    )
    response_style: OptionalPrompt = Field(
        default=None,
        max_length=MAX_INSTRUCTION_CHARS,
        description="Estilo de respuesta esperado por el operador.",
    )

    retrieve_context: bool | None = Field(
        default=None,
        description="Recuperar contexto de la base de conocimiento. None: usa el default del servicio.",
    )
    process_documents: bool | None = Field(
        default=None,
        description="Procesar el contenido completo de los documentos adjuntos. None: usa el default del servicio.",
    )

    @model_validator(mode="after")
    def validate_request(self) -> "AgentRequest":
        if self.messages[-1].role != MessageRole.human:
            raise ValueError("The last message must be from the human role.")
        return self

    model_config = {"frozen": True, "extra": "forbid"}
