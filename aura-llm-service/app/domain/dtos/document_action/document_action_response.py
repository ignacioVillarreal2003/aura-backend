from typing import Optional

from pydantic import BaseModel, Field, model_validator

from app.domain.constants.document_action_type import DocumentActionType
from app.domain.field_limits import MAX_ID, MAX_DOCUMENT_IDS_PER_REQUEST, MAX_INSTRUCTION_CHARS, MAX_CONTENT_CHARS
from app.infrastructure.http.document_context_provider.dtos.fragment_response import FragmentResponse


class DocumentActionResponse(BaseModel):
    result: str = Field(..., min_length=1, max_length=MAX_CONTENT_CHARS)
    document_ids: list[int] = Field(..., min_length=1, max_length=MAX_DOCUMENT_IDS_PER_REQUEST)
    instruction: str = Field(..., min_length=1, max_length=MAX_INSTRUCTION_CHARS)
    action: Optional[DocumentActionType] = Field(default=None)
    fragments: list[FragmentResponse] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_response(self) -> "DocumentActionResponse":
        if any(doc_id <= 0 or doc_id > MAX_ID for doc_id in self.document_ids):
            raise ValueError("Each document identifier must be a positive integer within the valid range.")
        if len(self.document_ids) != len(set(self.document_ids)):
            raise ValueError("Document identifiers must not contain duplicates.")
        return self

    model_config = {
        "from_attributes": True
    }
