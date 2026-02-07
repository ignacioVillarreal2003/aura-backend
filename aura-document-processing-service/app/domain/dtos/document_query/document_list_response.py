from typing import List
from pydantic import BaseModel, Field

from app.domain.dtos.document_query.document_response import DocumentResponse


class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse] = Field(
        default_factory=list
    )
