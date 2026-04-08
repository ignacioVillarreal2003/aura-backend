from pydantic import BaseModel

from app.domain.dtos.document.document_query.document_response import DocumentResponse


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]

    model_config = {
        "from_attributes": True
    }
