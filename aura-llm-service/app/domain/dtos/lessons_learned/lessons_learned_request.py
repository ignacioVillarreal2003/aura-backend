from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from app.domain.constants.message_role import MessageRole
from app.domain.dtos.message import Message
from app.domain.field_limits import MAX_ID, MAX_MESSAGES_IN_REQUEST


class LessonsLearnedMode(StrEnum):
    DIRECT = "direct"
    RAG = "rag"


class LessonsLearnedGenerateRequest(BaseModel):
    mode: LessonsLearnedMode = Field(
        ...,
        description=(
            "direct: genera el análisis solo con el texto provisto por el usuario. "
            "rag: enriquece con fragmentos de los documentos del usuario."
        ),
    )
    messages: list[Message] = Field(
        ...,
        min_length=1,
        max_length=MAX_MESSAGES_IN_REQUEST,
        description=(
            "Historial de conversación. El último mensaje debe ser de rol 'human' "
            "con el relato de la operación/ejercicio o instrucción de refinamiento."
        ),
    )
    chat_id: Optional[int] = Field(
        default=None,
        gt=0,
        le=MAX_ID,
        description="ID del chat fuente. En modo rag filtra los fragmentos a los documentos del chat.",
    )

    @model_validator(mode="after")
    def validate_last_message_is_human(self) -> "LessonsLearnedGenerateRequest":
        if self.messages[-1].role != MessageRole.human:
            raise ValueError("El último mensaje debe ser de rol 'human'.")
        return self

    model_config = {"frozen": True}
