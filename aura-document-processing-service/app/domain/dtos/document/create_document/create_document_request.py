from typing import Optional
from pydantic import BaseModel, Field

from app.domain.field_limits import MAX_ID
from app.domain.types import ChatId


class CreateDocumentRequest(BaseModel):
    chat_id: Optional[ChatId] = Field(default=None, gt=0, le=MAX_ID)
    prefer_docling: bool = False

    model_config = {
        "frozen": True,
    }
