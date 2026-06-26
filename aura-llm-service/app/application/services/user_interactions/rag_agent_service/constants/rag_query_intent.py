from enum import Enum


class RagQueryIntent(str, Enum):
    question = "question"
    document_lookup = "document_lookup"
    relational = "relational"
