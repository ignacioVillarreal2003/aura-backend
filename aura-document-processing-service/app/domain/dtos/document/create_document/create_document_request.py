from typing import Annotated, Optional
from pydantic import BaseModel, Field

from app.domain.field_limits import MAX_ID
from app.domain.types import ChatId


class CreateDocumentRequest(BaseModel):
    chat_id: Optional[Annotated[ChatId, Field(gt=0, le=MAX_ID)]] = None
    prefer_docling: bool = False

    model_config = {
        "frozen": True
    }
