from pydantic import BaseModel, Field


class DocumentsContextFragmentsRequest(BaseModel):
    document_ids: list[int] = Field(..., min_length=1)
