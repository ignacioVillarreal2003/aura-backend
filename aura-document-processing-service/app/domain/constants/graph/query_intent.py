from enum import Enum


class QueryIntent(str, Enum):
    """Structured intents the LLM may emit to translate a natural-language
    question into a parametrized graph query.

    The graph layer never executes raw Cypher emitted by the LLM. Instead,
    the LLM returns one of these intents plus a validated ``parameters``
    payload, and the service layer maps the intent to a parametrized
    Cypher template. This guarantees no Cypher injection is possible.
    """

    FIND_ENTITY = "find_entity"
    FIND_NEIGHBORS = "find_neighbors"
    FIND_PATH = "find_path"
    FILTER_BY_TYPE = "filter_by_type"
    UNKNOWN = "unknown"

    @classmethod
    def values(cls) -> list[str]:
        return [member.value for member in cls]
