from enum import Enum


class DocumentStatus(str, Enum):
    pending = "pending"
    published = "published"