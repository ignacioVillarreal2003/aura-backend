from pydantic import BaseModel, Field

from app.infrastructure.document_context_provider.dtos.context_fragments_response import ContextFragmentResponse


class DocumentSummaryResponse(BaseModel):
    document_id: int = Field(...)
    summary: str = Field(...)
    fragments: list[ContextFragmentResponse] = Field(default_factory=list)

    model_config = {
        "from_attributes": True
    }
