from pydantic import BaseModel, Field

from app.domain.constants.document_status import DocumentStatus


class DocumentResponseSchema(BaseModel):
    id: int = Field(...)
    title: str = Field(...)
    status: DocumentStatus = Field(...)