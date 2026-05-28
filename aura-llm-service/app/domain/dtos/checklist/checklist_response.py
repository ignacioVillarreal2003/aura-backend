from pydantic import BaseModel, Field

from app.domain.dtos.fragment.fragment_response import FragmentResponse
from app.domain.dtos.message import Message


class ChecklistItem(BaseModel):
    id: str = Field(..., description="UUID del ítem.")
    section: str = Field(..., description="Sección o fase a la que pertenece el ítem.")
    order: int = Field(..., ge=1, description="Posición dentro de la sección (empieza en 1).")
    text: str = Field(..., description="Descripción del paso a verificar.")
    is_checked: bool = Field(default=False, description="Estado de verificación.")
    notes: str = Field(default="", description="Notas opcionales sobre el ítem.")

    model_config = {"frozen": True}


class ChecklistGenerateResponse(BaseModel):
    title: str = Field(..., description="Título descriptivo de la checklist.")
    items: list[ChecklistItem] = Field(
        ...,
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
