from typing import Any, Optional
from pydantic import BaseModel, Field

from app.domain.field_limits import MAX_ID, MAX_JOB_ID_CHARS


class DocumentReprocessCommand(BaseModel):
    """Reprocess a document end-to-end from its stored object.

    Re-runs the full ingestion pipeline (re-download, re-chunk, re-embed) against the
    object already in storage: existing fragments are soft-deleted and replaced. Used
    to pick up new chunking/cleaning/splitting configuration without a re-upload.
    """
    document_id: int = Field(..., ge=1, le=MAX_ID)
    user: dict[str, Any] = Field(...)
    prefer_docling: bool = Field(default=False)
    post_process: bool = Field(default=True)
    post_process_graph: bool = Field(default=True)
    batch_id: Optional[str] = Field(default=None, max_length=MAX_JOB_ID_CHARS)
    auth_token: Optional[str] = Field(default=None, repr=False)

    model_config = {"frozen": True}
