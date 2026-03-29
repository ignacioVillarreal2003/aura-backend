from pydantic import BaseModel, Field


class DocumentIngestionCommand(BaseModel):
    document_id: int = Field(...)
    storage_url: str = Field(...)
    filename: str = Field(...)
    mime_type: str = Field(...)
    created_by: int = Field(...)
