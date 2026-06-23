from pydantic import BaseModel, Field

from app.domain.dtos.fragment.fragment_response import FragmentResponse
from app.domain.dtos.message import Message
from app.domain.field_limits import (
    MAX_CHECKLIST_ITEMS,
    MAX_CHECKLIST_ORDER,
    MAX_DESCRIPTION_CHARS,
    MAX_ITEM_TEXT_CHARS,
    MAX_SECTION_CHARS,
    MAX_TITLE_CHARS,
)


class ChecklistItem(BaseModel):
    section: str = Field(..., min_length=1, max_length=MAX_SECTION_CHARS, description="Sección o fase a la que pertenece el ítem.")
    order: int = Field(..., ge=1, le=MAX_CHECKLIST_ORDER, description="Posición dentro de la sección (empieza en 1).")
    text: str = Field(..., min_length=1, max_length=MAX_ITEM_TEXT_CHARS, description="Descripción del paso a verificar.")
    is_checked: bool = Field(default=False, description="Estado de verificación.")

    model_config = {"frozen": True}


class ChecklistGenerateResponse(BaseModel):
    title: str = Field(..., min_length=1, max_length=MAX_TITLE_CHARS, description="Título descriptivo de la checklist.")
    description: str = Field(default="", max_length=MAX_DESCRIPTION_CHARS, description="Breve descripción del propósito de la checklist.")
    items: list[ChecklistItem] = Field(
        ...,
        max_length=MAX_CHECKLIST_ITEMS,
        description="Ítems de la checklist ordenados y agrupados por sección.",
    )
    messages: list[Message] = Field(
        ...,
        description="Historial actualizado incluyendo la respuesta del asistente.",
    )
    fragments: list[FragmentResponse] = Field(
        default_factory=list,
        description="Fragmentos documentales utilizados como contexto (solo en modo rag).",
    )
    degraded_stages: list[str] = Field(
        default_factory=list,
        description=(
            "Etapas del pipeline de contexto que se degradaron (una dependencia falló y se "
            "continuó sin ella). Si no está vacío, la respuesta puede ser parcial."
        ),
    )
