from pydantic import BaseModel, Field

from app.domain.dtos.fragment.fragment_response import FragmentResponse
from app.domain.dtos.message import Message
from app.domain.dtos.report.report_request import ReportType


class ReportGenerateResponse(BaseModel):
    report_type: ReportType = Field(..., description="Tipo de informe generado.")
    content: str = Field(..., description="Contenido completo del informe en formato markdown.")
    messages: list[Message] = Field(
        ...,
        description="Historial actualizado incluyendo la respuesta del asistente.",
    )
    fragments: list[FragmentResponse] = Field(
        default_factory=list,
        description="Fragmentos documentales utilizados como contexto (solo en modo rag).",
    )
