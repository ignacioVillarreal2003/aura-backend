from enum import Enum


class DocumentStatus(str, Enum):
    uploaded = "uploaded"
    processing = "processing"
    processed = "processed"
    failed = "failed"
