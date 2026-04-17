from pydantic import BaseModel, Field, model_validator


class DocumentsContextFragmentsRequest(BaseModel):
    document_ids: list[int] = Field(..., min_length=1, max_length=50)

    @model_validator(mode="after")
    def validate_document_ids(self) -> "DocumentsContextFragmentsRequest":
        invalid_ids = [doc_id for doc_id in self.document_ids if doc_id <= 0]
        if invalid_ids:
            raise ValueError("Each document identifier must be a positive integer.")
        return self
