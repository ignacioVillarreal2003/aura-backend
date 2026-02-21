from typing import List
from pydantic import BaseModel, Field

from app.domain.dtos.document_query.document_query_response import DocumentQueryResponse


class DocumentQueryListResponse(BaseModel):
    documents: List[DocumentQueryResponse] = Field(
        default_factory=list
    )
