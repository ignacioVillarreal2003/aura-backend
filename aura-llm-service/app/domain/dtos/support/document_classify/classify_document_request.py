from pydantic import BaseModel, Field


class ClassifyDocumentRequest(BaseModel):
    document_name: str = Field(...)
    content: str = Field(...)
