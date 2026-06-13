from __future__ import annotations
from enum import Enum


class ProcessingStatus(str, Enum):
    """State of an asynchronous post-processing stage (enrichment / graph).

    ``pending``      -> the stage is required and has not finished yet.
    ``processed``    -> the stage completed successfully.
    ``failed``       -> the stage ran but failed.
    ``not_required`` -> the caller opted out, so the stage will never run.
    """

    pending = "pending"
    processed = "processed"
    failed = "failed"
    not_required = "not_required"

    @classmethod
    def values(cls) -> list[str]:
        return [member.value for member in cls]
