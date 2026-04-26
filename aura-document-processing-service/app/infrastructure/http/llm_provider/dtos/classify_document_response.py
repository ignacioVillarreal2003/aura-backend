from pydantic import BaseModel, Field

from app.domain.constants.document.document_type import DocumentType
from app.domain.field_limits import MAX_CATEGORY_CHARS, MAX_DESCRIPTION_CHARS


class ClassifyDocumentResponse(BaseModel):
    type: DocumentType = Field(...)
    category: str = Field(..., max_length=MAX_CATEGORY_CHARS)
    description: str = Field(..., max_length=MAX_DESCRIPTION_CHARS)
