from pydantic import BaseModel, Field

from app.domain.field_limits import MAX_LLM_CLASSIFY_CONTENT_CHARS, MAX_LLM_DOCUMENT_NAME_CHARS


class ClassifyDocumentRequest(BaseModel):
    document_name: str = Field(..., min_length=1, max_length=MAX_LLM_DOCUMENT_NAME_CHARS)
    content: str = Field(..., min_length=1, max_length=MAX_LLM_CLASSIFY_CONTENT_CHARS)
