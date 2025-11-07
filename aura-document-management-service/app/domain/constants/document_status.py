from enum import Enum


class DocumentStatus(str, Enum):
    pending = "pending"
    done = "done",
    failed = "failed"