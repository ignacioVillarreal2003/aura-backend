from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator

from app.domain.constants.document_action_type import DocumentActionType
from app.domain.field_limits import MAX_ID, MAX_DOCUMENT_IDS_PER_REQUEST, MAX_INSTRUCTION_CHARS
from app.domain.validation import OptionalPrompt, stripped_non_blank


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

    model_config = {"frozen": True, "extra": "forbid"}
