from typing import Any, Optional
from pydantic import BaseModel, Field

from app.domain.field_limits import MAX_ID, MAX_JOB_ID_CHARS


class DocumentReembedCommand(BaseModel):
    document_id: int = Field(..., ge=1, le=MAX_ID)
    user: dict[str, Any] = Field(...)
    batch_id: Optional[str] = Field(default=None, max_length=MAX_JOB_ID_CHARS)
    auth_token: Optional[str] = Field(default=None, repr=False)

    model_config = {"frozen": True}
