from pydantic import BaseModel, Field

from app.domain.constants.document_status import DocumentStatus
from app.domain.constants.document_type import DocumentType


class DocumentResponse(BaseModel):
    id: int = Field(...)
    name: str = Field(...)
    type: DocumentType = Field(...)
    status: DocumentStatus = Field(...)
    path: str = Field(...)
