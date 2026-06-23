from pydantic import BaseModel, Field, field_validator

from app.domain.field_limits import MAX_DESCRIPTION_CHARS, MAX_SUMMARY_CHARS, MAX_TITLE_CHARS
from app.domain.validation import stripped_non_blank
from app.infrastructure.http.document_context_provider.dtos.fragment_response import FragmentResponse


class DocumentSummaryResponse(BaseModel):
    title: str = Field(default="", max_length=MAX_TITLE_CHARS)
    description: str = Field(default="", max_length=MAX_DESCRIPTION_CHARS)
    summary: str = Field(..., min_length=1, max_length=MAX_SUMMARY_CHARS)
    fragments: list[FragmentResponse] = Field(default_factory=list)
    degraded_stages: list[str] = Field(
        default_factory=list,
        description=(
            "Etapas del pipeline de contexto que se degradaron (una dependencia falló y se "
            "continuó sin ella). Si no está vacío, la respuesta puede ser parcial."
        ),
    )

    @field_validator("summary")
    @classmethod
    def _strip_summary(cls, value: str) -> str:
        return stripped_non_blank(value, "Summary must not be blank.")

    model_config = {
        "from_attributes": True
    }
