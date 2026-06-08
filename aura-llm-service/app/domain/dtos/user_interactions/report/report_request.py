from enum import StrEnum
from pydantic import BaseModel, Field, field_validator, model_validator

from app.domain.constants.message_role import MessageRole
from app.domain.dtos.message import Message
from app.domain.field_limits import MAX_ID, MAX_MESSAGES_IN_REQUEST


class ReportType(StrEnum):
    SITREP = "SITREP"
    INTSUM = "INTSUM"
    OPORD = "OPORD"


class ReportMode(StrEnum):
    DIRECT = "direct"
    RAG = "rag"


class ReportGenerateRequest(BaseModel):
    report_type: ReportType = Field(..., description="Tipo de informe a generar.")
    mode: ReportMode = Field(
        ...,
        description=(
            "direct: genera el informe solo con el input del usuario. "
            "rag: enriquece con fragmentos de los documentos del usuario."
        ),
    )
    messages: list[Message] = Field(
        ...,
        min_length=1,
        max_length=MAX_MESSAGES_IN_REQUEST,
        description=(
            "Historial de conversación. El último mensaje debe ser de rol 'human' "
            "con el contenido operacional o instrucción de retoque."
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

    @field_validator("document_ids")
    @classmethod
    def _validate_document_ids(cls, value: list[int]) -> list[int]:
        if any(doc_id <= 0 for doc_id in value):
            raise ValueError("Cada document_id debe ser un entero positivo.")
        return value

    @model_validator(mode="after")
    def validate_last_message_is_human(self) -> "ReportGenerateRequest":
        if self.messages[-1].role != MessageRole.human:
            raise ValueError("El último mensaje debe ser de rol 'human'.")
        return self

    model_config = {"frozen": True}
