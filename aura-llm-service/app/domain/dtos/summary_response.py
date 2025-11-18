from pydantic import BaseModel, Field


class SummaryResponse(BaseModel):
    document_id: int = Field(...)
    summary: str = Field(...)
