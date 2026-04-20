from pydantic import BaseModel, Field


class ClassifyDocumentRequest(BaseModel):
    document_name: str = Field(..., min_length=1, max_length=2048)
    content: str = Field(..., min_length=1, max_length=50_000_000)
