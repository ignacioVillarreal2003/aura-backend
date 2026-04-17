from pydantic import BaseModel, Field, model_validator


class PostProcessFragmentsRequest(BaseModel):
    document_ids: list[int] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_document_ids(self) -> "PostProcessFragmentsRequest":
        if any(doc_id <= 0 for doc_id in self.document_ids):
            raise ValueError("Each document identifier must be a positive integer.")
        if len(self.document_ids) != len(set(self.document_ids)):
            raise ValueError("Document identifiers must not contain duplicates.")
        return self
