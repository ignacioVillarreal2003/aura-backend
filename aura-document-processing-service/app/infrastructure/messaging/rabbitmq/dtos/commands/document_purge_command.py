from typing import Any, Optional
from pydantic import BaseModel, Field

from app.domain.field_limits import MAX_ID, MAX_STORAGE_URL_CHARS


class DocumentPurgeCommand(BaseModel):
    document_id: int = Field(..., ge=1, le=MAX_ID)
    storage_url: str = Field(..., max_length=MAX_STORAGE_URL_CHARS)
    user: dict[str, Any] = Field(...)
    auth_token: Optional[str] = Field(default=None, repr=False)

    model_config = {"frozen": True}
