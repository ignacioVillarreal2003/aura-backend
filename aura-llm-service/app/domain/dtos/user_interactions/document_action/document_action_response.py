from typing import Optional
from pydantic import BaseModel, Field

from app.domain.constants.document_action_type import DocumentActionType
from app.domain.field_limits import MAX_CONTENT_CHARS, MAX_DESCRIPTION_CHARS, MAX_INSTRUCTION_CHARS, MAX_TITLE_CHARS
from app.infrastructure.http.document_context_provider.dtos.fragment_response import FragmentResponse


class DocumentActionResponse(BaseModel):
    title: str = Field(default="", max_length=MAX_TITLE_CHARS)
    description: str = Field(default="", max_length=MAX_DESCRIPTION_CHARS)
    result: str = Field(..., min_length=1, max_length=MAX_CONTENT_CHARS)
    instruction: str = Field(..., min_length=1, max_length=MAX_INSTRUCTION_CHARS)
    action: Optional[DocumentActionType] = Field(default=None)
    fragments: list[FragmentResponse] = Field(default_factory=list)
    degraded_stages: list[str] = Field(
        default_factory=list,
        description=(
            "Etapas del pipeline de contexto que se degradaron (una dependencia falló y se "
            "continuó sin ella). Si no está vacío, la respuesta puede ser parcial."
        ),
    )

    model_config = {
        "from_attributes": True
    }
