from pydantic import BaseModel, Field


class FragmentsByDocumentRequest(BaseModel):
    document_id: int = Field(
        ...,
        gt=0
    )
