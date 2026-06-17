from typing import Optional
from pydantic import BaseModel, Field


class DocumentChunk(BaseModel):
    """A chunk of a document together with its structural provenance.

    ``text`` is the chunk content to embed and store. The remaining fields are
    best-effort structural metadata derived from the source document (e.g. via
    Docling provenance) and may be ``None`` when the chunker cannot resolve them.
    """

    text: str = Field(..., min_length=1)

    page_number: Optional[int] = Field(default=None, ge=1)
    section_path: Optional[str] = Field(default=None)
    heading: Optional[str] = Field(default=None)
    char_start: Optional[int] = Field(default=None, ge=0)
    char_end: Optional[int] = Field(default=None, ge=0)
    bbox: Optional[dict] = Field(default=None)

    model_config = {"frozen": True}
