from typing import Any
from pydantic import BaseModel, Field, field_validator, model_validator

from app.domain.constants.graph.entity_type import EntityType
from app.domain.field_limits import MAX_ENTITY_NAME_CHARS
from app.domain.dtos.graph.graph_field_limits import MAX_RELATION_TYPE_CHARS


class ExtractedRelationEndpoint(BaseModel):
    name: str = Field(..., min_length=1, max_length=MAX_ENTITY_NAME_CHARS)
    type: EntityType = Field(...)

    @field_validator("name", mode="after")
    @classmethod
    def trim_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("endpoint name must not be blank.")
        return v


class ExtractedRelation(BaseModel):
    type: str = Field(..., min_length=1, max_length=MAX_RELATION_TYPE_CHARS)
    source: ExtractedRelationEndpoint = Field(...)
    target: ExtractedRelationEndpoint = Field(...)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    @model_validator(mode="before")
    @classmethod
    def coerce_string_endpoints(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        out = dict(data)
        for key in ("source", "target"):
            raw = out.get(key)
            if isinstance(raw, str):
                name = raw.strip()
                if not name:
                    raise ValueError(f"relation {key} must not be blank.")
                out[key] = {"name": name, "type": EntityType.OTHER.value}
            elif isinstance(raw, dict) and raw.get("name") is not None and "type" not in raw:
                merged = dict(raw)
                merged["type"] = EntityType.OTHER.value
                out[key] = merged
        return out

    @field_validator("type", mode="after")
    @classmethod
    def trim_type(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("relation type must not be blank.")
        return v
