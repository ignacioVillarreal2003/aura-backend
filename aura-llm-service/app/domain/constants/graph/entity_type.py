from enum import Enum


class EntityType(str, Enum):
    """Canonical taxonomy of entity types accepted by the graph extraction
    endpoint.

    Mirrors the document-processing-service ``EntityType`` so the LLM
    contract is identical on both sides. Anything that does not fit one of
    these buckets must be mapped to ``OTHER``.
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
