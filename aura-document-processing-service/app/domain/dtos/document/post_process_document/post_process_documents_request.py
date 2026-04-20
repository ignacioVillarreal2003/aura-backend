from pydantic import BaseModel, Field, model_validator

MAX_DOCUMENT_IDS = 500
MAX_ID = 2_147_483_647


class PostProcessDocumentsRequest(BaseModel):
    document_ids: list[int] = Field(..., min_length=1, max_length=MAX_DOCUMENT_IDS)

    @model_validator(mode="after")
    def validate_document_ids(self) -> "PostProcessDocumentsRequest":
        if any(doc_id <= 0 or doc_id > MAX_ID for doc_id in self.document_ids):
            raise ValueError("Each document identifier must be a positive integer within the valid range.")
        if len(self.document_ids) != len(set(self.document_ids)):
            raise ValueError("Document identifiers must not contain duplicates.")
        return self
