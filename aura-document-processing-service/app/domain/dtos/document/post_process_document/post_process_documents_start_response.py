from pydantic import BaseModel, Field


class PostProcessDocumentsStartResponse(BaseModel):
    message: str = Field(...)
    total_documents: int = Field(...)
