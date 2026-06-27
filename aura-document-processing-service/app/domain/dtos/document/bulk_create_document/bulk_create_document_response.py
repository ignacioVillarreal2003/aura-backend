from typing import Optional
from pydantic import BaseModel, Field

from app.domain.field_limits import (
    MAX_BULK_CREATE_DOCUMENTS,
    MAX_ERROR_MESSAGE_CHARS,
    MAX_ID,
    MAX_NAME_CHARS,
    MIN_FILE_SIZE_BYTES,
)
from app.domain.types import DocumentId


class BulkCreateDocumentItem(BaseModel):
    """Per-file outcome of a bulk-create request.

    A file either succeeds (``status == "created"`` with the created document
    fields populated) or fails (``status == "failed"`` with ``error`` set). The
    ``filename`` is always echoed back so the caller can correlate each item
    with the file it submitted, regardless of ordering."""

    status: str = Field(..., min_length=1, max_length=16)
    filename: Optional[str] = Field(default=None, max_length=MAX_NAME_CHARS)
    id: Optional[DocumentId] = Field(default=None, gt=0, le=MAX_ID)
    name: Optional[str] = Field(default=None, min_length=1, max_length=MAX_NAME_CHARS)
    mime_type: Optional[str] = Field(default=None, min_length=1, max_length=64)
    document_status: Optional[str] = Field(default=None, min_length=1, max_length=64)
    file_size_bytes: Optional[int] = Field(default=None, ge=MIN_FILE_SIZE_BYTES)
    error: Optional[str] = Field(default=None, max_length=MAX_ERROR_MESSAGE_CHARS)

    model_config = {
        "frozen": True,
    }


class BulkCreateDocumentResponse(BaseModel):
    """Aggregate result of a bulk-create request.

    ``created + failed == total`` always holds. The request as a whole succeeds
    (HTTP 201) even when some individual files fail, so callers must inspect
    ``items`` to know which uploads to retry."""

    total: int = Field(..., ge=0, le=MAX_BULK_CREATE_DOCUMENTS)
    created: int = Field(..., ge=0, le=MAX_BULK_CREATE_DOCUMENTS)
    failed: int = Field(..., ge=0, le=MAX_BULK_CREATE_DOCUMENTS)
    items: list[BulkCreateDocumentItem] = Field(
        default_factory=list, max_length=MAX_BULK_CREATE_DOCUMENTS
    )

    model_config = {
        "frozen": True,
    }
