from pydantic import BaseModel, Field

from app.domain.dtos.fragment.fragment_response import FragmentResponse
from app.domain.dtos.message import Message


class DecisionBriefOption(BaseModel):
    title: str = Field(..., description="Título corto de la opción.")
    description: str = Field(default="", description="Descripción de la opción.")
    pros: str = Field(default="", description="Argumentos a favor.")
    cons: str = Field(default="", description="Argumentos en contra.")
    is_recommended: bool = Field(
        default=False,
        description="Marca la opción respaldada por la recomendación final.",
    )

    model_config = {"frozen": True}


class DecisionBriefGenerateResponse(BaseModel):
    title: str = Field(..., description="Título descriptivo del brief de decisión.")
    problem: str = Field(default="", description="Planteo del problema o decisión a tomar.")
    context: str = Field(default="", description="Contexto y antecedentes relevantes.")
    risks: str = Field(default="", description="Riesgos identificados.")
    recommendation: str = Field(default="", description="Recomendación ejecutiva final.")
    options: list[DecisionBriefOption] = Field(..., description="Opciones analizadas.")
    messages: list[Message] = Field(
        ...,
        description="Historial actualizado incluyendo la respuesta del asistente.",
    )
    fragments: list[FragmentResponse] = Field(
        default_factory=list,
        description="Fragmentos documentales utilizados como contexto (solo en modo rag).",
    )
