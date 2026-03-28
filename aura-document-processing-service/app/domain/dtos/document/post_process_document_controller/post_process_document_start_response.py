from pydantic import BaseModel, Field


class PostProcessDocumentStartResponse(BaseModel):
    message: str = Field(...)
    total_documents: int = Field(...)
