from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.infrastructure.http.document_context_provider.dtos.fragment_response import FragmentResponse

_MAX_FRAGMENTS_IN_LIST = 1_000
_MAX_TOTAL_FRAGMENTS_LIST_CHARS = 300_000


class FragmentSectionGroup(BaseModel):
    primary: FragmentResponse
    section_fragments: list[FragmentResponse] = Field(
        default_factory=list,
        max_length=_MAX_FRAGMENTS_IN_LIST,
    )

    model_config = {
        "from_attributes": True,
        "frozen": True,
        "extra": "ignore",
    }


class FragmentListResponse(BaseModel):
    fragments: list[FragmentResponse] = Field(
        default_factory=list,
        max_length=_MAX_FRAGMENTS_IN_LIST,
    )

    groups: Optional[list[FragmentSectionGroup]] = Field(
        default=None,
        max_length=_MAX_FRAGMENTS_IN_LIST,
    )

    @field_validator("fragments")
    @classmethod
    def _validate_fragments(cls, fragments: list[FragmentResponse]) -> list[FragmentResponse]:
        seen_ids: set[int] = set()
        for fragment in fragments:
            if fragment.id in seen_ids:
                raise ValueError(f"Duplicate fragment id detected: {fragment.id}")
            seen_ids.add(fragment.id)

        result: list[FragmentResponse] = []
        total_chars = 0
        for fragment in fragments:
            remaining = _MAX_TOTAL_FRAGMENTS_LIST_CHARS - total_chars
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
        "extra": "ignore",
    }
