from pydantic import BaseModel, Field, model_validator

from app.domain.field_limits import MAX_DOCUMENT_NAME_CHARS, MAX_CONTENT_CHARS


class ClassifyDocumentRequest(BaseModel):
    document_name: str = Field(..., min_length=1, max_length=MAX_DOCUMENT_NAME_CHARS)
    content: str = Field(..., min_length=1, max_length=MAX_CONTENT_CHARS)

    @model_validator(mode="after")
    def validate_request(self) -> "ClassifyDocumentRequest":
        document_name = self.document_name.strip()
        if not document_name:
            raise ValueError("Document name must not be blank.")
        content = self.content.strip()
        if not content:
            raise ValueError("Content must not be blank.")
        updates = {}
        if document_name != self.document_name:
            updates["document_name"] = document_name
        if content != self.content:
            updates["content"] = content
        if updates:
            return self.model_copy(update=updates)
        return self

    model_config = {"frozen": True}
