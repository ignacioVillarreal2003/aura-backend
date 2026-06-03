from enum import StrEnum

from pydantic import BaseModel, Field

from app.domain.dtos.fragment.fragment_response import FragmentResponse
from app.domain.dtos.message import Message


class LessonCategory(StrEnum):
    SUSTAIN = "sustain"
    IMPROVE = "improve"
    RECOMMENDATION = "recommendation"


class LessonsLearnedItem(BaseModel):
    category: LessonCategory = Field(
        ...,
        description="Categoría: sustain (sostener), improve (mejorar) o recommendation (recomendación).",
    )
    observation: str = Field(..., description="Observación o hallazgo concreto.")
    discussion: str = Field(default="", description="Discusión o análisis del hallazgo.")
    recommendation: str = Field(default="", description="Acción recomendada asociada.")

    model_config = {"frozen": True}


class LessonsLearnedGenerateResponse(BaseModel):
    title: str = Field(..., description="Título descriptivo de las lecciones aprendidas.")
    context: str = Field(default="", description="Contexto de la operación o ejercicio analizado.")
    what_went_well: str = Field(default="", description="Resumen narrativo de lo que funcionó bien.")
    what_failed: str = Field(default="", description="Resumen narrativo de lo que falló.")
    recommendations: str = Field(default="", description="Resumen narrativo de las recomendaciones.")
    items: list[LessonsLearnedItem] = Field(..., description="Lecciones individuales clasificadas por categoría.")
    messages: list[Message] = Field(
        ...,
        description="Historial actualizado incluyendo la respuesta del asistente.",
    )
    fragments: list[FragmentResponse] = Field(
        default_factory=list,
        description="Fragmentos documentales utilizados como contexto (solo en modo rag).",
    )
