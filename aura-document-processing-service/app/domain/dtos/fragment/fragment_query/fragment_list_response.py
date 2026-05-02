from pydantic import BaseModel, Field, field_validator

from app.domain.dtos.document.document_query.document_response import DocumentResponse
from app.domain.dtos.fragment.fragment_query.fragment_response import FragmentResponse
from app.domain.field_limits import (
    MAX_FRAGMENTS_IN_LIST,
    MAX_TOTAL_FRAGMENTS_LIST_CHARS,
)


class FragmentListResponse(BaseModel):
    fragments: list[FragmentResponse] = Field(default_factory=list, max_length=MAX_FRAGMENTS_IN_LIST)
    documents: list[DocumentResponse] = Field(default_factory=list)

    @field_validator("fragments", mode="after")
    @classmethod
    def unique_ids_and_cap_total_fragment_chars(cls, v: list[FragmentResponse]) -> list[FragmentResponse]:
        seen_ids: set[int] = set()
        for fragment in v:
            if fragment.id in seen_ids:
                raise ValueError(f"Duplicate fragment id detected: {fragment.id}")
            seen_ids.add(fragment.id)

        result: list[FragmentResponse] = []
        total_chars = 0
        for fragment in v:
            remaining = MAX_TOTAL_FRAGMENTS_LIST_CHARS - total_chars
            if remaining <= 0:
                break
            if len(fragment.content) <= remaining:
                result.append(fragment)
                total_chars += len(fragment.content)
            else:
                result.append(
                    fragment.model_copy(update={"content": fragment.content[:remaining]})
                )
                break

        return result

    model_config = {
        "from_attributes": True,
        "frozen": True,
    }
