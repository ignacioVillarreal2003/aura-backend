from pydantic import BaseModel, Field

from app.domain.field_limits import MAX_ID, MAX_ERROR_MESSAGE_CHARS
from app.domain.types import DocumentId


class PostProcessDocumentError(BaseModel):
    document_id: DocumentId = Field(..., gt=0, le=MAX_ID)
    error: str = Field(..., min_length=1, max_length=MAX_ERROR_MESSAGE_CHARS)

    model_config = {"frozen": True}
