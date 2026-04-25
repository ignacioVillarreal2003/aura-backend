from pydantic import BaseModel, Field, model_validator

from app.domain.field_limits import MAX_ID, MAX_CONTEXT_QUERY_DOCUMENT_IDS


class DocumentsContextFragmentsRequest(BaseModel):
    document_ids: list[int] = Field(..., min_length=1, max_length=MAX_CONTEXT_QUERY_DOCUMENT_IDS)

    @model_validator(mode="after")
    def validate_document_ids(self) -> "DocumentsContextFragmentsRequest":
        if any(doc_id <= 0 or doc_id > MAX_ID for doc_id in self.document_ids):
            raise ValueError("Each document identifier must be a positive integer within the valid range.")
        if len(self.document_ids) != len(set(self.document_ids)):
            raise ValueError("Document identifiers must not contain duplicates.")
        return self

    model_config = {"frozen": True}
