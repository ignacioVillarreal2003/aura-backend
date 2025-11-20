from pydantic import BaseModel, Field


class SummaryRequest(BaseModel):
    fragments: list[str] = Field(...)