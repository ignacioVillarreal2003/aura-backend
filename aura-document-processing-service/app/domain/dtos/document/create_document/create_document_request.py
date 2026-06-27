from typing import Optional
from pydantic import BaseModel, Field

from app.domain.field_limits import MAX_ID, MAX_NAME_CHARS
from app.domain.types import ChatId


class CreateDocumentRequest(BaseModel):
    chat_id: Optional[ChatId] = Field(default=None, gt=0, le=MAX_ID)
    prefer_docling: bool = True
    enrich: bool = False
    graph_extract: bool = False
    name: Optional[str] = Field(default=None, max_length=MAX_NAME_CHARS)
    # description is intentionally omitted: it is generated automatically by the
    # enrichment pipeline and cannot be provided at creation.

    model_config = {
        "frozen": True,
    }
