from enum import Enum


class EmbeddingStatus(str, Enum):
    pending = "pending"
    published = "complete"