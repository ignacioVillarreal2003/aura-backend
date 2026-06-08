from pydantic import BaseModel, Field, model_validator

from app.domain.field_limits import MAX_ID, MAX_DOCUMENT_IDS_PER_REQUEST, MAX_SUMMARY_CHARS
from app.infrastructure.http.document_context_provider.dtos.fragment_response import FragmentResponse


class DocumentSummaryResponse(BaseModel):
    document_ids: list[int] = Field(..., min_length=1, max_length=MAX_DOCUMENT_IDS_PER_REQUEST)
    summary: str = Field(..., min_length=1, max_length=MAX_SUMMARY_CHARS)
    fragments: list[FragmentResponse] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_response(self) -> "DocumentSummaryResponse":
        if any(doc_id <= 0 or doc_id > MAX_ID for doc_id in self.document_ids):
            raise ValueError("Each document identifier must be a positive integer within the valid range.")
        if len(self.document_ids) != len(set(self.document_ids)):
            raise ValueError("Document identifiers must not contain duplicates.")
        summary = self.summary.strip()
        if not summary:
            raise ValueError("Summary must not be blank.")
        if summary != self.summary:
            return self.model_copy(update={"summary": summary})
        return self

    model_config = {
        "from_attributes": True
    }
