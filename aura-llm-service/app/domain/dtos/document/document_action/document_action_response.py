from typing import Optional

from pydantic import BaseModel, Field

from app.domain.constants.document_action_type import DocumentActionType


class DocumentActionResponse(BaseModel):
    result: str = Field(...)
    document_ids: list[int] = Field(...)
    action: Optional[DocumentActionType] = Field(default=None)

    model_config = {
        "from_attributes": True
    }
