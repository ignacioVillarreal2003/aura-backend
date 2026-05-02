"""Length and cardinality limits for knowledge-graph DTOs.

These constants are used by Pydantic models to bound any data that flows
through the public API or the LLM contracts. They protect Neo4j from
ever-growing payloads (e.g. malicious prompts emitting thousands of
entities per fragment) and keep responses predictable.
"""
from typing import Final

MAX_ENTITY_NAME_CHARS: Final[int] = 200
MAX_ENTITY_DESCRIPTION_CHARS: Final[int] = 2_000
MAX_ENTITY_ALIASES: Final[int] = 20
MAX_ENTITY_ALIAS_CHARS: Final[int] = 200

MAX_ENTITIES_PER_FRAGMENT: Final[int] = 50
MAX_RELATIONS_PER_FRAGMENT: Final[int] = 100

MAX_QUERY_QUESTION_CHARS: Final[int] = 4_000
MAX_QUERY_RESULTS: Final[int] = 200

MAX_PATH_HOPS: Final[int] = 6
MAX_PATHS_RETURNED: Final[int] = 25

MAX_ENTITY_TYPE_CHARS: Final[int] = 64
MAX_RELATION_TYPE_CHARS: Final[int] = 64

MAX_GRAPH_QUERY_PARAMETER_KEYS: Final[int] = 32

MAX_KNOWLEDGE_GRAPH_ERRORS: Final[int] = 1_000
MAX_KG_ERROR_MESSAGE_CHARS: Final[int] = 2_000
