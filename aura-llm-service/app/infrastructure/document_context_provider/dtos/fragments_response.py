from typing import List

from pydantic import BaseModel, Field, field_validator


class FragmentsResponse(BaseModel):
    context_fragments: List[str] = Field(
        default_factory=list
    )

    @field_validator('context_fragments')
    @classmethod
    def validate_context_fragments_list(cls,
                                v: List[str]) -> List[str]:
        if not isinstance(v, list):
            raise ValueError("context_fragments must be a list")

        for idx, item in enumerate(v):
            if not isinstance(item, str):
                raise ValueError(
                    f"Context fragment at index {idx} is not a string (type: {type(item).__name__})"
                )

        return v

    model_config = {
        "extra": "ignore"
    }
