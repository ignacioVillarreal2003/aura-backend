from enum import Enum


class QueryIntent(str, Enum):
    """Structured intents the LLM may emit when translating a natural
    language question over the knowledge graph.

    The graph layer never executes raw Cypher emitted by the LLM. The LLM
    returns one of these intents plus a validated ``parameters`` payload
    and the document-processing service maps each intent to a parametrized
    Cypher template. This guarantees no Cypher injection is possible.
    """

    FIND_ENTITY = "find_entity"
    FIND_NEIGHBORS = "find_neighbors"
    FIND_PATH = "find_path"
    FILTER_BY_TYPE = "filter_by_type"
    LIST_BY_DOCUMENT = "list_by_document"
    UNKNOWN = "unknown"

    @classmethod
    def values(cls) -> list[str]:
        return [member.value for member in cls]
