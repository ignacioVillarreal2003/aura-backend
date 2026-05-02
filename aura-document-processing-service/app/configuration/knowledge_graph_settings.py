from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.domain.constants.graph.entity_type import EntityType
from app.domain.constants.graph.relation_type import DEFAULT_ALLOWED_RELATION_TYPES


class KnowledgeGraphSettings(BaseSettings):
    """Master configuration for the knowledge-graph module.

    The module is fully optional: when ``enabled`` is False the rest of
    the application starts up without any of the KG dependencies (Neo4j,
    KG consumers, KG endpoints).
    """

    model_config = SettingsConfigDict(
        env_prefix="KNOWLEDGE_GRAPH_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    enabled: bool = Field(default=False)

    extraction_max_fragments_per_document: int = Field(default=500, ge=1, le=10_000)
    extraction_concurrency: int = Field(
        default=1,
        ge=1,
        le=32,
        description="Parallel fragment extractions per document job; prefer 1 for slow local Ollama.",
    )
    extraction_lock_ttl_seconds: int = Field(default=1800, ge=60, le=86_400)
    extraction_snapshot_ttl_seconds: int = Field(default=86_400, ge=60, le=2_592_000)

    query_default_results: int = Field(default=20, ge=1, le=200)
    query_max_results: int = Field(default=200, ge=1, le=1000)
    query_default_neighbor_depth: int = Field(default=1, ge=1, le=4)
    query_max_neighbor_depth: int = Field(default=3, ge=1, le=6)

    accessible_documents_max: int = Field(default=10_000, ge=1, le=1_000_000)

    hybrid_intent_confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    hybrid_min_kg_results: int = Field(default=1, ge=0, le=100)

    allowed_entity_types: Optional[str] = Field(
        default=None,
        description=(
            "Optional comma-separated list of entity types restricting what "
            "the extraction LLM is allowed to emit. When unset, the full "
            "EntityType enum is allowed."
        ),
    )
    allowed_relation_types: Optional[str] = Field(
        default=None,
        description=(
            "Optional comma-separated list of relation types restricting "
            "what the extraction LLM is allowed to emit. When unset, the "
            "default whitelist DEFAULT_ALLOWED_RELATION_TYPES is used."
        ),
    )

    system_principal_email: str = Field(
        default="kg-extraction@system.local",
        min_length=3,
        max_length=254,
        description=(
            "Email used to identify event-triggered (non user-driven) "
            "extraction jobs in audit logs. The trust mechanism is the "
            "service API key; this email is propagated for traceability."
        ),
    )
    system_principal_roles: Optional[str] = Field(
        default=None,
        description=(
            "Optional comma-separated roles propagated to the LLM service "
            "for event-triggered extraction calls."
        ),
    )
    system_principal_permissions: Optional[str] = Field(
        default=None,
        description=(
            "Optional comma-separated permissions propagated to the LLM "
            "service for event-triggered extraction calls. The LLM service "
            "should rely on the service API key for trust; this is for audit."
        ),
    )

    def resolve_system_principal_roles(self) -> list[str]:
        if not self.system_principal_roles:
            return []
        return [r.strip() for r in self.system_principal_roles.split(",") if r.strip()]

    def resolve_system_principal_permissions(self) -> list[str]:
        if not self.system_principal_permissions:
            return []
        return [
            p.strip()
            for p in self.system_principal_permissions.split(",")
            if p.strip()
        ]

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
