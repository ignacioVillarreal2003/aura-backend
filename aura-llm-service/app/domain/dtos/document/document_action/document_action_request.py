from typing import Optional

from pydantic import BaseModel, Field

from app.domain.constants.document_action_type import DocumentActionType


class DocumentActionRequest(BaseModel):
    document_ids: list[int] = Field(...)
    instruction: str = Field(...)
    action: Optional[DocumentActionType] = Field(default=None)
