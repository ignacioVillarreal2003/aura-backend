from typing import Optional
from pydantic import BaseModel, Field

from app.domain.field_limits import MAX_ID, MAX_NAME_CHARS, MAX_DESCRIPTION_CHARS
from app.domain.types import ChatId


class CreateDocumentRequest(BaseModel):
    chat_id: Optional[ChatId] = Field(default=None, gt=0, le=MAX_ID)
    prefer_docling: bool = False
    post_process: bool = False
    post_process_graph: bool = False
    name: Optional[str] = Field(default=None, max_length=MAX_NAME_CHARS)
    description: Optional[str] = Field(default=None, max_length=MAX_DESCRIPTION_CHARS)

    model_config = {
        "frozen": True,
    }
