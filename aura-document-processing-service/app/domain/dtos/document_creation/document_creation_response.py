from pydantic import BaseModel, Field

from app.domain.constants.document_status import DocumentStatus


class DocumentCreationResponse(BaseModel):
    status: DocumentStatus = Field(...)
