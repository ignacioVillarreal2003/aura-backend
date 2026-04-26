from __future__ import annotations
from enum import Enum


class DocumentStatus(str, Enum):
    uploaded = "uploaded"
    processed = "processed"
    failed = "failed"

    @classmethod
    def allowed_transitions(cls) -> dict[DocumentStatus, frozenset[DocumentStatus]]:
        return {
            cls.uploaded: frozenset({cls.processed, cls.failed}),
            cls.processed: frozenset(),
            cls.failed: frozenset(),
        }

    def can_transition_to(self, target: DocumentStatus) -> bool:
        return target in self.allowed_transitions()[self]

    def transition_to(self, target: DocumentStatus) -> None:
        if self == target:
            return
        if not self.can_transition_to(target):
            raise ValueError(
                f"Invalid document status transition: {self.value} -> {target.value}"
            )
