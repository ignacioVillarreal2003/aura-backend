from pydantic import BaseModel, Field, model_validator

from app.domain.field_limits import MAX_ID, MAX_POST_PROCESS_DOCUMENT_IDS


class PostProcessDocumentsRequest(BaseModel):
    document_ids: list[int] = Field(..., min_length=1, max_length=MAX_POST_PROCESS_DOCUMENT_IDS)

    @model_validator(mode="after")
    def check_doc_ids_in_range(self) -> "PostProcessDocumentsRequest":
        if any(doc_id <= 0 or doc_id > MAX_ID for doc_id in self.document_ids):
            raise ValueError("All document_id values must be in the allowed range for identifiers.")
        if len(self.document_ids) != len(set(self.document_ids)):
            raise ValueError("Document identifiers must not contain duplicates.")
        return self

    model_config = {"frozen": True}
