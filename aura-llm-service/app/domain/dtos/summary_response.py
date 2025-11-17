from pydantic import BaseModel, Field


class SummaryResponse(BaseModel):
    document_id: str = Field(...)
    summary: str = Field(...)
