from pydantic import BaseModel, Field


class DocumentSummaryRequest(BaseModel):
    document_id: int = Field(
        ...
    )