"""Length and cardinality limits for knowledge-graph DTOs.

Mirrors the limits defined in the document-processing-service so both
sides of the HTTP contract enforce the same bounds.
"""
from typing import Final

MAX_ENTITY_NAME_CHARS: Final[int] = 200
MAX_ENTITY_DESCRIPTION_CHARS: Final[int] = 2_000
MAX_ENTITY_ALIASES: Final[int] = 20
MAX_ENTITY_ALIAS_CHARS: Final[int] = 200

MAX_ENTITIES_PER_FRAGMENT: Final[int] = 50
MAX_RELATIONS_PER_FRAGMENT: Final[int] = 100

MAX_QUERY_QUESTION_CHARS: Final[int] = 4_000

MAX_ENTITY_TYPE_CHARS: Final[int] = 64
MAX_RELATION_TYPE_CHARS: Final[int] = 64

MAX_GRAPH_QUERY_PARAMETER_KEYS: Final[int] = 32
