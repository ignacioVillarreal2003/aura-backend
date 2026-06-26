from pydantic import BaseModel, Field

from app.domain.dtos.fragment.fragment_response import FragmentResponse
from app.domain.dtos.message import Message
from app.domain.field_limits import (
    MAX_DESCRIPTION_CHARS,
    MAX_ITEM_TEXT_CHARS,
    MAX_OCCURRED_LABEL_CHARS,
    MAX_TIMELINE_EVENT_CHARS,
    MAX_TIMELINE_EVENTS,
    MAX_TITLE_CHARS,
)


class TimelineEvent(BaseModel):
    title: str = Field(..., min_length=1, max_length=MAX_TIMELINE_EVENT_CHARS, description="Título del evento.")
    description: str = Field(
        default="", max_length=MAX_ITEM_TEXT_CHARS, description="Descripción del evento en formato Markdown."
    )
    occurred_label: str = Field(
        default="",
        max_length=MAX_OCCURRED_LABEL_CHARS,
        description="Referencia temporal del evento en lenguaje natural (p. ej. '3 de mayo 14:30', 'madrugada del 3').",
    )

    model_config = {"frozen": True}


class TimelineGenerateResponse(BaseModel):
    title: str = Field(..., min_length=1, max_length=MAX_TITLE_CHARS, description="Título descriptivo de la línea de tiempo.")
    description: str = Field(
        default="", max_length=MAX_DESCRIPTION_CHARS, description="Enunciado que sintetiza de qué trata la cronología."
    )
    events: list[TimelineEvent] = Field(
        ...,
        min_length=1,
        max_length=MAX_TIMELINE_EVENTS,
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
    degraded_stages: list[str] = Field(
        default_factory=list,
        description=(
            "Etapas del pipeline de contexto que se degradaron (una dependencia falló y se "
            "continuó sin ella). Si no está vacío, la respuesta puede ser parcial."
        ),
    )
