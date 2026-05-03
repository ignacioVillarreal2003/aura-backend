from typing import Optional
from pydantic import BaseModel, Field, model_validator

from app.domain.constants.graph.entity_type import EntityType
from app.domain.field_limits import MAX_ENTITY_NAME_CHARS, MAX_PATH_HOPS
from app.domain.dtos.graph.graph_field_limits import MAX_PATHS_RETURNED


class FindPathRequest(BaseModel):
    source_name: str = Field(..., min_length=1, max_length=MAX_ENTITY_NAME_CHARS)
    target_name: str = Field(..., min_length=1, max_length=MAX_ENTITY_NAME_CHARS)
    source_type: Optional[EntityType] = Field(default=None)
    target_type: Optional[EntityType] = Field(default=None)
    max_hops: int = Field(default=4, ge=1, le=MAX_PATH_HOPS)
    max_paths: int = Field(default=10, ge=1, le=MAX_PATHS_RETURNED)
    only_shortest: bool = Field(default=False)

    model_config = {"frozen": True}

    @model_validator(mode="after")
    def validate_endpoints(self) -> "FindPathRequest":
        source = self.source_name.strip()
        target = self.target_name.strip()
        if not source:
            raise ValueError("source_name must not be blank.")
        if not target:
            raise ValueError("target_name must not be blank.")
        if source.lower() == target.lower() and self.source_type == self.target_type:
            raise ValueError("source and target endpoints must be different entities.")
        if source != self.source_name or target != self.target_name:
            return self.model_copy(update={"source_name": source, "target_name": target})
        return self
