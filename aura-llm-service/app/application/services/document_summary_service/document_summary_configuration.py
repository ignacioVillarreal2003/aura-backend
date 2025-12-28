from dataclasses import dataclass
from enum import Enum
from typing import Optional

from app.application.exceptions.app_exceptions import ValidationError


class SummarizationStrategy(str, Enum):
    DIRECT = "direct"
    MAP_REDUCE = "map_reduce"


@dataclass(frozen=True)
class DocumentSummaryConfiguration:
    large_document_threshold: int = 5

    chunk_size: int = 5
    max_concurrent_chunks: int = 3
    max_retry_attempts: int = 3
    retry_delay: float = 1.0

    system_prompt: Optional[str] = None

    MIN_DOCUMENT_ID: int = 1

    MIN_LARGE_DOCUMENT_THRESHOLD: int = 2
    MAX_LARGE_DOCUMENT_THRESHOLD: int = 50

    MIN_CHUNK_SIZE: int = 1
    MAX_CHUNK_SIZE: int = 20

    MIN_CONCURRENT_CHUNKS: int = 1
    MAX_CONCURRENT_CHUNKS: int = 10

    DEFAULT_SYSTEM_PROMPT: str = (
        "Eres un asistente experto en crear resúmenes precisos y concisos de documentos. "
        "Tu tarea es analizar el contenido proporcionado y generar un resumen claro, "
        "estructurado y completo que capture los puntos principales sin perder información importante. "
        "El resumen debe estar en formato Markdown e incluir títulos (`#`), subtítulos (`##`), "
        "listas (`-`) y negritas (`**`) cuando sea apropiado."
    )

    def __post_init__(self):
        self._validate()

    def _validate(self) -> None:
        self._validate_large_document_threshold()
        self._validate_chunk_size()
        self._validate_max_concurrent_chunks()

    def _validate_large_document_threshold(self) -> None:
        if not (
                self.MIN_LARGE_DOCUMENT_THRESHOLD <= self.large_document_threshold <= self.MAX_LARGE_DOCUMENT_THRESHOLD):
            raise ValidationError(
                f"large_document_threshold must be between {self.MIN_LARGE_DOCUMENT_THRESHOLD} and {self.MAX_LARGE_DOCUMENT_THRESHOLD}",
                status_code=500
            )

    def _validate_chunk_size(self) -> None:
        if not (self.MIN_CHUNK_SIZE <= self.chunk_size <= self.MAX_CHUNK_SIZE):
            raise ValidationError(
                f"chunk_size must be between {self.MIN_CHUNK_SIZE} and {self.MAX_CHUNK_SIZE}",
                status_code=500
            )

    def _validate_max_concurrent_chunks(self) -> None:
        if not (self.MIN_CONCURRENT_CHUNKS <= self.max_concurrent_chunks <= self.MAX_CONCURRENT_CHUNKS):
            raise ValidationError(
                f"max_concurrent_chunks must be between {self.MIN_CONCURRENT_CHUNKS} and {self.MAX_CONCURRENT_CHUNKS}",
                status_code=500
            )

    @property
    def effective_system_prompt(self) -> str:
        return self.system_prompt or self.DEFAULT_SYSTEM_PROMPT

    def select_strategy(self,
                        fragment_count: int) -> SummarizationStrategy:
        if fragment_count > self.large_document_threshold:
            return SummarizationStrategy.MAP_REDUCE
        return SummarizationStrategy.DIRECT
