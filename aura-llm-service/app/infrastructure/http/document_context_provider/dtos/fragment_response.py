from typing import Any, Optional
from pydantic import BaseModel, Field, computed_field, field_validator

_MAX_ID = 2_147_483_647
_MAX_NAME_CHARS = 255
_MAX_DESCRIPTION_CHARS = 2_000
_MAX_CATEGORY_CHARS = 100
_MAX_FRAGMENT_CONTENT_CHARS = 50_000
_MAX_FRAGMENT_INDEX = 100_000
_MAX_SECTION_PATH_CHARS = 1_024
_MAX_HEADING_CHARS = 512


class FragmentEmbeddedDocument(BaseModel):
    id: int = Field(..., gt=0, le=_MAX_ID)
    name: str = Field(..., min_length=1, max_length=_MAX_NAME_CHARS)
    description: Optional[str] = Field(default=None, min_length=1, max_length=_MAX_DESCRIPTION_CHARS)
    type: Optional[str] = Field(default=None, max_length=64)
    category: Optional[str] = Field(default=None, min_length=1, max_length=_MAX_CATEGORY_CHARS)

    @field_validator("name", mode="after")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("name must not be blank.")
        return s

    @field_validator("description", mode="before")
    @classmethod
    def normalize_description(cls, v: object) -> object:
        if not isinstance(v, str):
            return v
        stripped = v.strip()
        return stripped or None

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, v: object) -> object:
        if not isinstance(v, str):
            return v
        stripped = v.strip()
        return stripped or None

    model_config = {
        "from_attributes": True,
        "frozen": True,
    }


class FragmentResponse(BaseModel):
    id: int = Field(..., gt=0, le=_MAX_ID)
    content: str = Field(..., min_length=1, max_length=_MAX_FRAGMENT_CONTENT_CHARS)
    contextualized_content: Optional[str] = Field(default=None, max_length=_MAX_FRAGMENT_CONTENT_CHARS)
    fragment_index: int = Field(..., ge=0, le=_MAX_FRAGMENT_INDEX)

    page_number: Optional[int] = Field(default=None, ge=1)
    section_path: Optional[str] = Field(default=None, max_length=_MAX_SECTION_PATH_CHARS)
    heading: Optional[str] = Field(default=None, max_length=_MAX_HEADING_CHARS)
    char_start: Optional[int] = Field(default=None, ge=0)
    char_end: Optional[int] = Field(default=None, ge=0)
    bbox: Optional[dict[str, Any]] = Field(default=None)

    document: FragmentEmbeddedDocument = Field(...)

    @computed_field
    @property
    def document_id(self) -> int:
        return self.document.id

    @property
    def effective_content(self) -> str:
        return self.contextualized_content or self.content

    @field_validator("content", mode="before")
    @classmethod
    def sanitize_content(cls, v: object) -> object:
        if not isinstance(v, str):
            return v
        content = v.strip()
        if not content:
            raise ValueError("content must not be blank.")
        return content[:_MAX_FRAGMENT_CONTENT_CHARS]

    @field_validator("contextualized_content", mode="before")
    @classmethod
    def sanitize_contextualized_content(cls, v: object) -> Optional[str]:
        if not isinstance(v, str):
            return v
        contextualized = v.strip()
        return contextualized[:_MAX_FRAGMENT_CONTENT_CHARS] if contextualized else None

    @field_validator("section_path", mode="before")
    @classmethod
    def sanitize_section_path(cls, v: object) -> Optional[str]:
        if not isinstance(v, str):
            return v
        section_path = v.strip()
        return section_path[:_MAX_SECTION_PATH_CHARS] if section_path else None

    @field_validator("heading", mode="before")
    @classmethod
    def sanitize_heading(cls, v: object) -> Optional[str]:
        if not isinstance(v, str):
            return v
        heading = v.strip()
        return heading[:_MAX_HEADING_CHARS] if heading else None

    model_config = {
        "from_attributes": True,
        "frozen": True,
    }
