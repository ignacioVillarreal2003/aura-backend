from pydantic import BaseModel, Field


class ContextFragmentsByDocumentRequest(BaseModel):
    document_id: int = Field(...)
