from enum import Enum


class QueryIntent(str, Enum):
    FIND_ENTITY = "find_entity"
    FIND_NEIGHBORS = "find_neighbors"
    FIND_PATH = "find_path"
    FILTER_BY_TYPE = "filter_by_type"
    LIST_BY_DOCUMENT = "list_by_document"
    UNKNOWN = "unknown"

    @classmethod
    def values(cls) -> list[str]:
        return [member.value for member in cls]
