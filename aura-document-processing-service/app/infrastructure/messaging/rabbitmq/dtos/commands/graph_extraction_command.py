from typing import Any, Optional
from pydantic import BaseModel, Field

from app.domain.field_limits import MAX_ID


class GraphExtractionCommand(BaseModel):
    document_id: int = Field(..., ge=1, le=MAX_ID)
    user: dict[str, Any] = Field(...)
    force: bool = Field(default=False)
    auth_token: Optional[str] = Field(default=None, repr=False)

    model_config = {"frozen": True}
