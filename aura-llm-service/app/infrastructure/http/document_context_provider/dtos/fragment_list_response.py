from pydantic import BaseModel, Field, model_validator

from app.infrastructure.http.document_context_provider.dtos.fragment_response import FragmentResponse

MAX_TOTAL_CHARS = 300_000


class FragmentListResponse(BaseModel):
    fragments: list[FragmentResponse] = Field(default_factory=list)

    model_config = {
        "from_attributes": True
    }

    @model_validator(mode="after")
    def validate_fragments(self) -> "FragmentListResponse":
        seen_ids: set[int] = set()
        for fragment in self.fragments:
            if fragment.id in seen_ids:
                raise ValueError(f"Duplicate fragment id detected: {fragment.id}")
            seen_ids.add(fragment.id)

        result: list[FragmentResponse] = []
        total_chars = 0
        for fragment in self.fragments:
            remaining = MAX_TOTAL_CHARS - total_chars
            if remaining <= 0:
                break
            if len(fragment.content) <= remaining:
                result.append(fragment)
                total_chars += len(fragment.content)
            else:
                result.append(fragment.model_copy(update={"content": fragment.content[:remaining]}))
                break

        self.fragments = result
        return self
