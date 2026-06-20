from typing import Optional
from pydantic import BaseModel, Field


class DocumentChunk(BaseModel):
    text: str = Field(..., min_length=1)

    embed_text: Optional[str] = Field(default=None, min_length=1)

    page_number: Optional[int] = Field(default=None, ge=1)
    section_path: Optional[str] = Field(default=None)
    heading: Optional[str] = Field(default=None)
    char_start: Optional[int] = Field(default=None, ge=0)
    char_end: Optional[int] = Field(default=None, ge=0)
    bbox: Optional[dict] = Field(default=None)

    model_config = {"frozen": True}
