from pydantic import BaseModel, Field

from app.domain.constants.document.document_type import DocumentType


class ClassifyDocumentResponse(BaseModel):
    type: DocumentType = Field(...)
    category: str = Field(...)
    description: str = Field(...)
