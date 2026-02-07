from enum import Enum


class DocumentStatus(str, Enum):
    PENDING = "pending"
    DONE = "done",
    FAILED = "failed"
