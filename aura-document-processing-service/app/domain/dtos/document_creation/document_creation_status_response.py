from pydantic import BaseModel, Field

from app.domain.constants.document_status import DocumentStatus


class DocumentCreationStatusResponse(BaseModel):
    document_id: int = Field(...)
    status: DocumentStatus = Field(...)
