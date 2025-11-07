from pydantic import BaseModel, Field

from app.domain.constants.document_status import DocumentStatus


class DocumentResponseSchema(BaseModel):
    id: int = Field(...)
    file_name: str = Field(...)
    status: DocumentStatus = Field(...)