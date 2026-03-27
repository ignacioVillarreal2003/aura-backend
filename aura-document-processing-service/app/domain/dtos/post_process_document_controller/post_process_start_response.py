from pydantic import BaseModel, Field


class PostProcessStartResponse(BaseModel):
    message: str = Field(...)
    total_documents: int = Field(...)
