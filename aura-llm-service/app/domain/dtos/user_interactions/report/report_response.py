from pydantic import BaseModel, Field

from app.domain.dtos.fragment.fragment_response import FragmentResponse
from app.domain.dtos.message import Message
from app.domain.dtos.user_interactions.report.report_request import ReportType
from app.domain.field_limits import MAX_REPORT_CONTENT_CHARS


class ReportGenerateResponse(BaseModel):
    report_type: ReportType = Field(..., description="Tipo de informe generado.")
    content: str = Field(..., min_length=1, max_length=MAX_REPORT_CONTENT_CHARS, description="Contenido completo del informe en formato markdown.")
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
