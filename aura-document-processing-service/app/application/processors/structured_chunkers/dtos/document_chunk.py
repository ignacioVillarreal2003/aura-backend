from typing import Optional
from pydantic import BaseModel, Field


class DocumentChunk(BaseModel):
    """A chunk of a document together with its structural provenance.

    ``text`` is the chunk content to store and display. ``embed_text`` is the
    variant fed to the embedder; structure-aware chunkers set it to a
    heading-contextualized serialization so a chunk carries its section anchor in
    the vector even when a concept is split at a chunk border. When unset (e.g.
    flat-text splitters) callers fall back to ``text``. The remaining fields are
    best-effort structural metadata derived from the source document (e.g. via
    Docling provenance) and may be ``None`` when the chunker cannot resolve them.
    """

    text: str = Field(..., min_length=1)

    embed_text: Optional[str] = Field(default=None, min_length=1)

    page_number: Optional[int] = Field(default=None, ge=1)
    section_path: Optional[str] = Field(default=None)
    heading: Optional[str] = Field(default=None)
    char_start: Optional[int] = Field(default=None, ge=0)
    char_end: Optional[int] = Field(default=None, ge=0)
    bbox: Optional[dict] = Field(default=None)

    model_config = {"frozen": True}
