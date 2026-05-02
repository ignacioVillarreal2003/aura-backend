from enum import Enum


class EntityType(str, Enum):
    """Canonical taxonomy of entity types stored in the knowledge graph.

    The taxonomy is intentionally compact: it covers the entity kinds an
    LLM can reliably identify at fragment level. Anything that does not
    fit one of these buckets is mapped to ``OTHER``. The ``allowed_entity_types``
    setting in ``KnowledgeGraphSettings`` can further restrict the set
    accepted by the LLM extraction call.
    """

    PERSON = "person"
    ORGANIZATION = "organization"
    LOCATION = "location"
    PRODUCT = "product"
    EVENT = "event"
    CONCEPT = "concept"
    DATE = "date"
    OTHER = "other"

    @classmethod
    def values(cls) -> list[str]:
        return [member.value for member in cls]

    @classmethod
    def parse(cls, value: str) -> "EntityType":
        normalized = (value or "").strip().lower()
        for member in cls:
            if member.value == normalized:
                return member
        return cls.OTHER
