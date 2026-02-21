from pydantic import BaseModel, Field


class UpdateDocumentRequest(BaseModel):
    is_active: str = Field()
