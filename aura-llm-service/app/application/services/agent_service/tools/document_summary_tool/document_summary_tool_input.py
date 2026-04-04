from pydantic import BaseModel, Field


class DocumentSummaryToolInput(BaseModel):
    document_id: int = Field(..., description="The ID of the document to summarize")
