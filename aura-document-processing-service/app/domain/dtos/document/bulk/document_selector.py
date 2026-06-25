from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator

from app.domain.field_limits import MAX_ID, MAX_POST_PROCESS_DOCUMENT_IDS


class DocumentSelector(BaseModel):
    document_ids: Optional[list[int]] = Field(
        default=None,
        max_length=MAX_POST_PROCESS_DOCUMENT_IDS,
        description="IDs concretos a procesar (1 o varios). Excluyente con all_documents.",
    )
    all_documents: bool = Field(
        default=False,
        description="Si True, procesa todos los documentos de la base (de a poco). Excluyente con document_ids.",
    )

    model_config = {"frozen": True}

    @field_validator("document_ids")
    @classmethod
    def _clean_ids(cls, v: Optional[list[int]]) -> Optional[list[int]]:
        if v is None:
            return None
        seen: list[int] = []
        for doc_id in v:
            if not isinstance(doc_id, int) or isinstance(doc_id, bool):
                raise ValueError("document_ids must contain integers.")
            if doc_id < 1 or doc_id > MAX_ID:
                raise ValueError(f"document_ids contains an out-of-range id: {doc_id}")
            if doc_id not in seen:
                seen.append(doc_id)
        if not seen:
            raise ValueError("document_ids must not be empty when provided.")
        return seen

    @model_validator(mode="after")
    def _exactly_one_mode(self) -> "DocumentSelector":
        if self.all_documents and self.document_ids:
            raise ValueError("Provide either 'document_ids' or 'all_documents', not both.")
        if not self.all_documents and not self.document_ids:
            raise ValueError("Provide either 'document_ids' or 'all_documents'.")
        return self
