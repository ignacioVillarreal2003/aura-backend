from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator

from app.domain.constants.document_action_type import DocumentActionType
from app.domain.field_limits import MAX_ID, MAX_DOCUMENT_IDS_PER_REQUEST, MAX_INSTRUCTION_CHARS
from app.domain.validation import stripped_non_blank


class DocumentActionRequest(BaseModel):
    document_ids: list[int] = Field(..., min_length=1, max_length=MAX_DOCUMENT_IDS_PER_REQUEST)
    instruction: str = Field(..., min_length=1, max_length=MAX_INSTRUCTION_CHARS)
    action: Optional[DocumentActionType] = Field(default=None)
    chat_id: int = Field(
        ...,
        gt=0,
        le=MAX_ID,
        description="ID del chat fuente. Informativo; el contexto se toma de document_ids.",
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

    @field_validator("instruction")
    @classmethod
    def _strip_instruction(cls, value: str) -> str:
        return stripped_non_blank(value, "Instruction must not be blank.")

    @model_validator(mode="after")
    def validate_request(self) -> "DocumentActionRequest":
        if any(doc_id <= 0 or doc_id > MAX_ID for doc_id in self.document_ids):
            raise ValueError("Each document identifier must be a positive integer within the valid range.")
        if len(self.document_ids) != len(set(self.document_ids)):
            raise ValueError("Document identifiers must not contain duplicates.")
        return self

    model_config = {"frozen": True}
