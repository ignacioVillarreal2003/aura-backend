from enum import StrEnum
from pydantic import BaseModel, Field, field_validator, model_validator

from app.domain.constants.message_role import MessageRole
from app.domain.dtos.message import Message
from app.domain.field_limits import MAX_ID, MAX_MESSAGES_IN_REQUEST, MAX_INSTRUCTION_CHARS


class ChecklistMode(StrEnum):
    DIRECT = "direct"
    RAG = "rag"


class ChecklistGenerateRequest(BaseModel):
    mode: ChecklistMode = Field(
        ...,
        description=(
            "direct: genera la checklist solo con el texto de procedimiento provisto. "
            "rag: enriquece con fragmentos de los documentos del usuario."
        ),
    )
    messages: list[Message] = Field(
        ...,
        min_length=1,
        max_length=MAX_MESSAGES_IN_REQUEST,
        description=(
            "Historial de conversación. El último mensaje debe ser de rol 'human' "
            "con el texto del procedimiento o instrucción de refinamiento."
        ),
    )
    chat_id: int = Field(
        ...,
        gt=0,
        le=MAX_ID,
        description="ID del chat fuente. En modo rag filtra los fragmentos a los documentos del chat.",
    )
    document_ids: list[int] = Field(
        default_factory=list,
        max_length=20,
        description=(
            "IDs de documentos a adjuntar como contexto prioritario. Se usan siempre "
            "(en modo direct y rag), además del input del usuario."
        ),
    )

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

    @field_validator("document_ids")
    @classmethod
    def _validate_document_ids(cls, value: list[int]) -> list[int]:
        if any(doc_id <= 0 for doc_id in value):
            raise ValueError("Cada document_id debe ser un entero positivo.")
        return value

    @model_validator(mode="after")
    def validate_last_message_is_human(self) -> "ChecklistGenerateRequest":
        if self.messages[-1].role != MessageRole.human:
            raise ValueError("El último mensaje debe ser de rol 'human'.")
        return self

    model_config = {"frozen": True}
