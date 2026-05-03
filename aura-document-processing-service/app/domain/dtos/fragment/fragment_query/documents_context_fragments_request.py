from pydantic import BaseModel, Field, field_validator, model_validator

from app.domain.field_limits import MAX_ID, MAX_CONTEXT_QUERY_DOCUMENT_IDS
from app.domain.types import DocumentId


class DocumentsContextFragmentsRequest(BaseModel):
    document_ids: list[DocumentId] = Field(
        ...,
        min_length=1,
        max_length=MAX_CONTEXT_QUERY_DOCUMENT_IDS,
    )

    @field_validator("document_ids", mode="after")
    @classmethod
    def validate_each_id(cls, v: list[DocumentId]) -> list[DocumentId]:
        for doc_id in v:
            if doc_id <= 0 or doc_id > MAX_ID:
                raise ValueError(
                    f"Document id {doc_id} is out of range (1–{MAX_ID})."
                )
        return v

    @model_validator(mode="after")
    def no_duplicates(self) -> "DocumentsContextFragmentsRequest":
        if len(self.document_ids) != len(set(self.document_ids)):
            raise ValueError("document_ids must not contain duplicates.")
        return self

    model_config = {"frozen": True}
