from pydantic import BaseModel, Field


class DocumentContextFragmentsRequest(BaseModel):
    document_id: int = Field(
        ...
    )
