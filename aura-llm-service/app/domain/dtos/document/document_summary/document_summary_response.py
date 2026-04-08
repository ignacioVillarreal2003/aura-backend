from pydantic import BaseModel, Field

from app.infrastructure.http.document_context_provider.dtos.fragment_response import FragmentResponse


class DocumentSummaryResponse(BaseModel):
    document_id: int = Field(...)
    summary: str = Field(...)
    fragments: list[FragmentResponse] = Field(default_factory=list)

    model_config = {
        "from_attributes": True
    }
