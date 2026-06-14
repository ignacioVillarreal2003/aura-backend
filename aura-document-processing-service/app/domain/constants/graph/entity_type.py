from enum import Enum


class EntityType(str, Enum):
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
