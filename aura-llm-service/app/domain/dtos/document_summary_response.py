from pydantic import BaseModel, Field


class DocumentSummaryResponse(BaseModel):
    summary: str = Field(...)
