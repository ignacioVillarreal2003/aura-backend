from pydantic import BaseModel, Field

from app.domain.dtos.fragment.fragment_response import FragmentResponse
from app.domain.dtos.message import Message
from app.domain.field_limits import (
    MAX_DECISION_BRIEF_OPTIONS,
    MAX_NOTES_CHARS,
    MAX_PROSE_CHARS,
    MAX_TITLE_CHARS,
)


class DecisionBriefOption(BaseModel):
    title: str = Field(..., min_length=1, max_length=MAX_TITLE_CHARS, description="Título corto de la opción.")
    pros: str = Field(default="", max_length=MAX_NOTES_CHARS, description="Argumentos a favor.")
    cons: str = Field(default="", max_length=MAX_NOTES_CHARS, description="Argumentos en contra.")
    is_recommended: bool = Field(
        default=False,
        description="Marca la opción respaldada por la recomendación final.",
    )

    model_config = {"frozen": True}


class DecisionBriefGenerateResponse(BaseModel):
    title: str = Field(..., min_length=1, max_length=MAX_TITLE_CHARS, description="Título descriptivo del brief de decisión.")
    description: str = Field(default="", max_length=MAX_PROSE_CHARS, description="Planteo del problema o decisión a tomar.")
    context: str = Field(default="", max_length=MAX_PROSE_CHARS, description="Contexto y antecedentes relevantes.")
    risks: str = Field(default="", max_length=MAX_PROSE_CHARS, description="Riesgos identificados.")
    recommendation: str = Field(default="", max_length=MAX_PROSE_CHARS, description="Recomendación ejecutiva final.")
    options: list[DecisionBriefOption] = Field(..., max_length=MAX_DECISION_BRIEF_OPTIONS, description="Opciones analizadas.")
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
