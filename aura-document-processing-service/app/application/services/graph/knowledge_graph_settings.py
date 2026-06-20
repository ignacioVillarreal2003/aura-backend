from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.domain.constants.graph.entity_type import EntityType
from app.domain.constants.graph.relation_type import DEFAULT_ALLOWED_RELATION_TYPES


class KnowledgeGraphSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="KNOWLEDGE_GRAPH_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    enabled: bool = Field(default=False)

    extraction_max_fragments_per_document: int = Field(default=500, ge=1, le=10_000)
    extraction_concurrency: int = Field(default=1, ge=1, le=32)
    extraction_sliding_window_chars: int = Field(default=500, ge=0, le=2000)
    extraction_lock_ttl_seconds: int = Field(default=1800, ge=60, le=86_400)

    query_default_results: int = Field(default=20, ge=1, le=200)
    query_max_results: int = Field(default=200, ge=1, le=1000)
    query_default_neighbor_depth: int = Field(default=1, ge=1, le=4)
    query_max_neighbor_depth: int = Field(default=3, ge=1, le=6)

    accessible_documents_max: int = Field(default=10_000, ge=1, le=1_000_000)

    context_max_entities: int = Field(default=8, ge=1, le=25)
    context_max_relations: int = Field(default=30, ge=1, le=100)
    context_max_chars: int = Field(default=4_000, ge=500, le=20_000)
    context_neighbor_depth: int = Field(default=1, ge=1, le=3)

    allowed_entity_types: Optional[str] = Field(default=None)
    allowed_relation_types: Optional[str] = Field(default=None)

    @field_validator("allowed_entity_types", "allowed_relation_types", mode="before")
    @classmethod
    def normalize_optional_csv(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = str(v).strip()
        return v or None

    def resolve_allowed_entity_types(self) -> list[str]:
        if self.allowed_entity_types is None:
            return EntityType.values()
        types = [
            t.strip().lower()
            for t in self.allowed_entity_types.split(",")
            if t and t.strip()
        ]
        valid = {t.value for t in EntityType}
        return [t for t in types if t in valid] or EntityType.values()

    def resolve_allowed_relation_types(self) -> list[str]:
        if self.allowed_relation_types is None:
            return list(DEFAULT_ALLOWED_RELATION_TYPES)
        return [
            t.strip().lower()
            for t in self.allowed_relation_types.split(",")
            if t and t.strip()
        ]
