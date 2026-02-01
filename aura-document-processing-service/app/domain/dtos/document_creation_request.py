from pydantic import BaseModel, Field


class DocumentCreationRequest(BaseModel):
    chat_id: int = Field(...)
