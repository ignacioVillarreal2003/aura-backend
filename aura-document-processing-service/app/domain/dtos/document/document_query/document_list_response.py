from pydantic import BaseModel, Field

from app.domain.dtos.document.document_query.document_response import DocumentResponse
from app.domain.field_limits import MAX_DOCUMENTS_IN_LIST


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse] = Field(default_factory=list, max_length=MAX_DOCUMENTS_IN_LIST)

    model_config = {
        "from_attributes": True,
        "frozen": True,
    }
