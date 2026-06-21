from enum import Enum


class DocumentSearchMode(str, Enum):
    vector = "vector"
    bm25 = "bm25"
