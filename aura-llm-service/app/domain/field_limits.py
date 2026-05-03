from typing import Final

# ─── Shared ────────────────────────────────────────────────────────────────────

MAX_ID: Final[int] = 2_147_483_647

# ─── Document ─────────────────────────────────────────────────────────────────

MAX_DOCUMENT_IDS_PER_REQUEST: Final[int] = 50
MAX_DOCUMENTS_IN_LIST: Final[int] = 10_000
MAX_CONTEXT_QUERY_DOCUMENT_IDS: Final[int] = 50

MAX_DOCUMENT_NAME_CHARS: Final[int] = 255
MAX_NAME_CHARS: Final[int] = 255

MAX_CATEGORY_CHARS: Final[int] = 100
MAX_DESCRIPTION_CHARS: Final[int] = 2_000
MAX_STORAGE_URL_CHARS: Final[int] = 1_024
MIN_FILE_SIZE_BYTES: Final[int] = 1
MAX_PROCESSOR_TYPE_CHARS: Final[int] = 100
MAX_SPLIT_SIZE: Final[int] = 100_000
MAX_SPLIT_OVERLAP: Final[int] = 99_999

# ─── Knowledge graph (HTTP controllers & shared KG field bounds) ─────────────

MAX_ENTITY_NAME_CHARS: Final[int] = 200
MAX_ENTITY_DESCRIPTION_CHARS: Final[int] = 2_000
MAX_ENTITY_ALIASES: Final[int] = 20
MAX_ENTITY_ALIAS_CHARS: Final[int] = 200

MAX_ENTITIES_PER_FRAGMENT: Final[int] = 50
MAX_RELATIONS_PER_FRAGMENT: Final[int] = 100

MAX_GRAPH_QUERY_QUESTION_CHARS: Final[int] = 4_000
MAX_GRAPH_QUERY_REASONING_CHARS: Final[int] = 2_000
MAX_GRAPH_QUERY_PARAMETER_KEYS: Final[int] = 32

MAX_GRAPH_ENTITY_TYPE_CHARS: Final[int] = 64
MAX_GRAPH_RELATION_TYPE_CHARS: Final[int] = 64

MAX_GRAPH_ENTITY_TYPES_PER_ONTOLOGY: Final[int] = 64
MAX_GRAPH_RELATION_TYPES_PER_ONTOLOGY: Final[int] = 128

# ─── General content & messages ──────────────────────────────────────────────

MAX_CONTENT_CHARS: Final[int] = 50_000
MAX_INSTRUCTION_CHARS: Final[int] = 10_000

MAX_MESSAGE_CONTENT_CHARS: Final[int] = 16_000
MAX_MESSAGES_IN_REQUEST: Final[int] = 50
MAX_HISTORY_MESSAGES: Final[int] = 49
MAX_QUESTION_CHARS: Final[int] = 16_000

MAX_MESSAGE_CHARS: Final[int] = 500
MAX_ERROR_MESSAGE_CHARS: Final[int] = 500

MAX_SUMMARY_CHARS: Final[int] = 10_000
MAX_TOPIC_CHARS: Final[int] = 500
MAX_TOPICS: Final[int] = 100
MAX_ENTITY_KEY_CHARS: Final[int] = 255
MAX_ENTITY_VALUE_CHARS: Final[int] = 1_000
MAX_ENTITY_KEYS: Final[int] = 200

# ─── Keywords, fragments & retrieval ───────────────────────────────────────────

MAX_KEYWORDS_CHARS: Final[int] = 16_000
MAX_FRAGMENT_INDEX: Final[int] = 100_000
MAX_FRAGMENTS_IN_LIST: Final[int] = 1_000
MAX_TOTAL_FRAGMENTS_LIST_CHARS: Final[int] = 300_000
MAX_FRAGMENTS_PER_QUERY_STRATEGY: Final[int] = 50
MAX_RERANK_FRAGMENTS: Final[int] = 100

# ─── Authentication / RBAC ───────────────────────────────────────────────────

MAX_EMAIL_CHARS: Final[int] = 254
MAX_ROLE_CHARS: Final[int] = 100
MAX_PERMISSION_CHARS: Final[int] = 100
MAX_ROLES: Final[int] = 50
MAX_PERMISSIONS: Final[int] = 200

# ─── Post-processing ───────────────────────────────────────────────────────────

MAX_POST_PROCESS_SNAPSHOT_ERRORS: Final[int] = 1_000
MAX_POST_PROCESS_DOCUMENT_IDS: Final[int] = 10_000
MAX_POST_PROCESS_FRAGMENTS_DOCUMENT_IDS: Final[int] = 500
