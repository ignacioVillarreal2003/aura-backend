import logging
from dataclasses import dataclass
from typing import Optional, Final

from app.application.services.document_summary_service.constants.summarization_strategy import SummarizationStrategy

logger = logging.getLogger(__name__)


@dataclass(
    frozen=True,
    kw_only=True
)
class DocumentSummaryConfiguration:
    MIN_LARGE_DOCUMENT_THRESHOLD: Final[int] = 2
    MAX_LARGE_DOCUMENT_THRESHOLD: Final[int] = 50

    MIN_CHUNK_SIZE: Final[int] = 1
    MAX_CHUNK_SIZE: Final[int] = 20

    MIN_CONCURRENT_CHUNKS: Final[int] = 1
    MAX_CONCURRENT_CHUNKS: Final[int] = 10

    MIN_RETRY_ATTEMPTS: Final[int] = 0
    MAX_RETRY_ATTEMPTS: Final[int] = 10

    MIN_RETRY_DELAY: Final[float] = 0.0
    MAX_RETRY_DELAY: Final[float] = 60.0

    DEFAULT_LARGE_DOCUMENT_THRESHOLD: Final[int] = 5
    DEFAULT_CHUNK_SIZE: Final[int] = 5
    DEFAULT_MAX_CONCURRENT_CHUNKS: Final[int] = 3
    DEFAULT_MAX_RETRY_ATTEMPTS: Final[int] = 3
    DEFAULT_RETRY_DELAY: Final[float] = 1.0
    DEFAULT_MIN_DOCUMENT_ID: Final[int] = 1
    DEFAULT_MAX_DOCUMENT_ID: Final[int] = 2_147_483_647

    large_document_threshold: int = DEFAULT_LARGE_DOCUMENT_THRESHOLD
    chunk_size: int = DEFAULT_CHUNK_SIZE
    max_concurrent_chunks: int = DEFAULT_MAX_CONCURRENT_CHUNKS
    max_retry_attempts: int = DEFAULT_MAX_RETRY_ATTEMPTS
    retry_delay: float = DEFAULT_RETRY_DELAY
    min_document_id: int = DEFAULT_MIN_DOCUMENT_ID
    max_document_id: int = DEFAULT_MAX_DOCUMENT_ID
    custom_system_prompt: Optional[str] = None

    def __post_init__(self) -> None:
        try:
            self._validate_all()
            logger.info("DocumentSummaryConfiguration initialized successfully")
        except ValueError as e:
            logger.error(
                "Configuration validation failed",
                extra={
                    "error": str(e)
                },
                exc_info=True
            )
            raise

    def _validate_all(self) -> None:
        self._validate_large_document_threshold()
        self._validate_chunk_size()
        self._validate_max_concurrent_chunks()
        self._validate_max_retry_attempts()
        self._validate_retry_delay()

    def _validate_large_document_threshold(self) -> None:
        if not (self.MIN_LARGE_DOCUMENT_THRESHOLD
                <= self.large_document_threshold
                <= self.MAX_LARGE_DOCUMENT_THRESHOLD):
            raise ValueError(
                f"large_document_threshold debe estar entre {self.MIN_LARGE_DOCUMENT_THRESHOLD} y {self.MAX_LARGE_DOCUMENT_THRESHOLD}, "
                f"se recibió: {self.large_document_threshold}"
            )

    def _validate_chunk_size(self) -> None:
        if not (self.MIN_CHUNK_SIZE
                <= self.chunk_size
                <= self.MAX_CHUNK_SIZE):
            raise ValueError(
                f"chunk_size debe estar entre {self.MIN_CHUNK_SIZE} y {self.MAX_CHUNK_SIZE}, "
                f"se recibió: {self.chunk_size}"
            )

    def _validate_max_concurrent_chunks(self) -> None:
        if not (self.MIN_CONCURRENT_CHUNKS
                <= self.max_concurrent_chunks
                <= self.MAX_CONCURRENT_CHUNKS):
            raise ValueError(
                f"max_concurrent_chunks debe estar entre {self.MIN_CONCURRENT_CHUNKS} y {self.MAX_CONCURRENT_CHUNKS}, "
                f"se recibió: {self.max_concurrent_chunks}"
            )

    def _validate_max_retry_attempts(self) -> None:
        if not (self.MIN_RETRY_ATTEMPTS
                <= self.max_retry_attempts
                <= self.MAX_RETRY_ATTEMPTS):
            raise ValueError(
                f"max_retry_attempts debe estar entre {self.MIN_RETRY_ATTEMPTS} y {self.MAX_RETRY_ATTEMPTS}, "
                f"se recibió: {self.max_retry_attempts}"
            )

    def _validate_retry_delay(self) -> None:
        if not (self.MIN_RETRY_DELAY
                <= self.retry_delay
                <= self.MAX_RETRY_DELAY):
            raise ValueError(
                f"retry_delay debe estar entre {self.MIN_RETRY_DELAY} y {self.MAX_RETRY_DELAY}, "
                f"se recibió: {self.retry_delay}"
            )

    def select_strategy(self,
                        fragment_count: int) -> SummarizationStrategy:
        if fragment_count > self.large_document_threshold:
            return SummarizationStrategy.MAP_REDUCE
        return SummarizationStrategy.DIRECT

    @property
    def system_prompt(self) -> str:
        return self.custom_system_prompt or self._get_default_system_prompt()

    @staticmethod
    def _get_default_system_prompt() -> str:
        return (
            "Eres un asistente experto en crear resúmenes precisos y concisos basados únicamente en el contenido proporcionado. "
            "REGLAS ESTRICTAS:\n"
            "1. Resume SOLO utilizando la información presente en el contenido provisto\n"
            "2. No agregues, infieras ni asumas información que no esté explícitamente en el texto\n"
            "3. Si una sección del contenido no aporta información relevante, omítela del resumen\n"
            "4. Prioriza los puntos clave, conceptos principales y conclusiones importantes\n"
            "5. Mantén el resumen claro, estructurado y fácil de leer\n"
            "6. Usa formato Markdown: títulos (#), subtítulos (##), listas (-), negritas (**), tablas cuando corresponda\n"
            "7. Sé conciso, pero sin perder información esencial\n"
        )
