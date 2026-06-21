from __future__ import annotations
from enum import Enum


class ProcessingStatus(str, Enum):
    pending = "pending"
    processed = "processed"
    failed = "failed"
    not_required = "not_required"

    @classmethod
    def values(cls) -> list[str]:
        return [member.value for member in cls]
