from pydantic import BaseModel, Field, field_validator

from app.domain.constants.document_type import DocumentType
from app.domain.field_limits import MAX_CATEGORY_CHARS, MAX_DESCRIPTION_CHARS
from app.domain.validation import stripped_non_blank


class ClassifyDocumentResponse(BaseModel):
    type: DocumentType = Field(...)
    category: str = Field(..., min_length=1, max_length=MAX_CATEGORY_CHARS)
    description: str = Field(..., min_length=1, max_length=MAX_DESCRIPTION_CHARS)

    @field_validator("category")
    @classmethod
    def _strip_category(cls, value: str) -> str:
        return stripped_non_blank(value, "Category must not be blank.")

    @field_validator("description")
    @classmethod
    def _strip_description(cls, value: str) -> str:
        return stripped_non_blank(value, "Description must not be blank.")

    model_config = {
        "from_attributes": True
    }
