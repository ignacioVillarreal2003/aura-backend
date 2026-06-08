from pydantic import BaseModel, Field, model_validator

from app.domain.constants.document_type import DocumentType
from app.domain.field_limits import MAX_CATEGORY_CHARS, MAX_DESCRIPTION_CHARS


class ClassifyDocumentResponse(BaseModel):
    type: DocumentType = Field(...)
    category: str = Field(..., min_length=1, max_length=MAX_CATEGORY_CHARS)
    description: str = Field(..., min_length=1, max_length=MAX_DESCRIPTION_CHARS)

    @model_validator(mode="after")
    def validate_response(self) -> "ClassifyDocumentResponse":
        category = self.category.strip()
        if not category:
            raise ValueError("Category must not be blank.")
        description = self.description.strip()
        if not description:
            raise ValueError("Description must not be blank.")
        updates = {}
        if category != self.category:
            updates["category"] = category
        if description != self.description:
            updates["description"] = description
        if updates:
            return self.model_copy(update=updates)
        return self

    model_config = {
        "from_attributes": True
    }
