from typing import Any, Optional
from pydantic import BaseModel, Field

from app.domain.field_limits import MAX_ID


class DocumentReembedCommand(BaseModel):
    """Re-embed a document's existing fragments with the currently-active model.

    Keeps the chunk text as-is and only regenerates the vectors, so it is the safe
    migration path when the embedding model changes (see audit C-2/C-4). When
    ``force`` is False only fragments whose stored ``embedding_model`` differs from
    the active model are re-embedded (idempotent); when True every fragment is
    re-embedded regardless.
    """
    document_id: int = Field(..., ge=1, le=MAX_ID)
    user: dict[str, Any] = Field(...)
    force: bool = Field(default=False)
    auth_token: Optional[str] = Field(default=None, repr=False)

    model_config = {"frozen": True}
