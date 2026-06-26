from pydantic import BaseModel, Field, field_validator, model_validator

from app.domain.constants.message_role import MessageRole
from app.domain.dtos.message import Message
from app.domain.field_limits import (
    MAX_DOCUMENT_IDS_PER_REQUEST,
    MAX_HISTORY_MESSAGES,
    MAX_ID,
    MAX_INSTRUCTION_CHARS,
    MAX_MESSAGES_IN_REQUEST,
)
from app.domain.validation import OptionalPrompt


class GeneralChatRequest(BaseModel):
    messages: list[Message] = Field(
        ...,
        min_length=1,
        max_length=MAX_MESSAGES_IN_REQUEST,
        description="Historial de conversación. El último mensaje debe ser de rol 'human'.",
    )
    chat_id: int = Field(
        ...,
        gt=0,
        le=MAX_ID,
        description="ID del chat fuente. En modo rag filtra los fragmentos a los documentos del chat.",
    )
    document_ids: list[int] = Field(
        default_factory=list,
        max_length=MAX_DOCUMENT_IDS_PER_REQUEST,
        description=(
            "IDs de documentos a adjuntar como contexto prioritario. Se usan siempre "
            "(en modo direct y rag), además del historial de conversación."
        ),
    )
    system_prompt: OptionalPrompt = Field(
        default=None,
        max_length=MAX_INSTRUCTION_CHARS,
        description="System prompt personalizado. Si no se provee se usa el prompt por defecto de AURA.",
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

    @field_validator("document_ids")
    @classmethod
    def _validate_document_ids(cls, value: list[int]) -> list[int]:
        if any(doc_id <= 0 for doc_id in value):
            raise ValueError("Cada document_id debe ser un entero positivo.")
        return value

    @model_validator(mode="after")
    def validate_request(self) -> "GeneralChatRequest":
        if self.messages[-1].role != MessageRole.human:
            raise ValueError("El último mensaje debe ser de rol 'human'.")
        history_count = len(self.messages) - 1
        if history_count > MAX_HISTORY_MESSAGES:
            raise ValueError(f"El historial no puede superar {MAX_HISTORY_MESSAGES} mensajes.")
        return self

    model_config = {"frozen": True, "extra": "forbid"}
