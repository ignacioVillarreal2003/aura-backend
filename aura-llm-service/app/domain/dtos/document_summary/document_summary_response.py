from pydantic import BaseModel, Field


class DocumentSummaryResponse(BaseModel):
    summary: str = Field(...)

    model_config = {
        "from_attributes": True
    }
