from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ContextFragmentResponse(BaseModel):
    id: int
    document_id: int
    content: str
    cleaned_content: str
    vector: list[float]
    fragment_index: int
    summary: Optional[str] = None
    entities: Optional[dict] = None
    topics: Optional[list[str]] = None
    created_by: int
    created_at: datetime
    deleted_by: Optional[int] = None
    deleted_at: Optional[datetime] = None

    model_config = {
        "from_attributes": True
    }
