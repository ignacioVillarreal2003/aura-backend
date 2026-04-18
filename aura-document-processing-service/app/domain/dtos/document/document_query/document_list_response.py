from pydantic import BaseModel, Field

from app.domain.dtos.document.document_query.document_response import DocumentResponse

MAX_DOCUMENTS = 10_000


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse] = Field(default_factory=list, max_length=MAX_DOCUMENTS)

    model_config = {
        "from_attributes": True
    }
