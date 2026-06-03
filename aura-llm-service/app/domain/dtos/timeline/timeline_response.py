from typing import Optional

from pydantic import BaseModel, Field

from app.domain.dtos.fragment.fragment_response import FragmentResponse
from app.domain.dtos.message import Message


class TimelineEvent(BaseModel):
    event: str = Field(..., description="Título corto del evento.")
    description: str = Field(default="", description="Descripción ampliada del evento.")
    occurred_at: Optional[str] = Field(
        default=None,
        description="Instante del evento en ISO 8601 (p. ej. '2024-05-03T14:30:00Z'). Null si se desconoce.",
    )
    occurred_label: str = Field(
        default="",
        description="Etiqueta temporal en lenguaje natural cuando no hay fecha exacta (p. ej. 'madrugada del 3').",
    )
    source_document_id: Optional[int] = Field(
        default=None,
        description="ID del documento fuente del que se extrajo el evento, si aplica.",
    )

    model_config = {"frozen": True}


class TimelineGenerateResponse(BaseModel):
    title: str = Field(..., description="Título descriptivo de la línea de tiempo.")
    summary: str = Field(default="", description="Resumen general de la cronología.")
    events: list[TimelineEvent] = Field(
        ...,
        description="Eventos ordenados cronológicamente.",
    )
    messages: list[Message] = Field(
        ...,
        description="Historial actualizado incluyendo la respuesta del asistente.",
    )
    fragments: list[FragmentResponse] = Field(
        default_factory=list,
        description="Fragmentos documentales utilizados como contexto (solo en modo rag).",
    )
