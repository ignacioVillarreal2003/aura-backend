from pydantic import BaseModel, Field


class DocumentSummaryRequest(BaseModel):
    documentId: int = Field(...)