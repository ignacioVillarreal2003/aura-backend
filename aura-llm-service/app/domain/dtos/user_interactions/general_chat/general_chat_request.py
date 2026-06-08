from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.domain.constants.message_role import MessageRole
from app.domain.dtos.message import Message
from app.domain.field_limits import MAX_HISTORY_MESSAGES, MAX_ID, MAX_INSTRUCTION_CHARS, MAX_MESSAGES_IN_REQUEST


class GeneralChatMode(StrEnum):
    DIRECT = "direct"
    RAG = "rag"


class GeneralChatRequest(BaseModel):
    mode: GeneralChatMode = Field(
        ...,
        description=(
            "direct: responde solo con el historial y los documentos adjuntos. "
            "rag: enriquece adicionalmente con fragmentos de los documentos del usuario."
        ),
    )
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
        max_length=20,
        description=(
            "IDs de documentos a adjuntar como contexto prioritario. Se usan siempre "
            "(en modo direct y rag), además del historial de conversación."
        ),
    )
    system_prompt: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=MAX_INSTRUCTION_CHARS,
        description="System prompt personalizado. Si no se provee se usa el prompt por defecto de AURA.",
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
        if self.system_prompt is not None:
            stripped = self.system_prompt.strip()
            if not stripped:
                raise ValueError("system_prompt no puede estar vacío si se provee.")
            if stripped != self.system_prompt:
                return self.model_copy(update={"system_prompt": stripped})
        return self

    model_config = {"frozen": True}
