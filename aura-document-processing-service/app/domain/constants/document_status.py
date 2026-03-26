from enum import Enum


class DocumentStatus(str, Enum):
    uploaded = "uploaded"
    processed = "processed"
    failed = "failed"
