import logging
from dataclasses import dataclass
from typing import Final

from app.application.exceptions.app_exception import ValidationError
from app.domain.constants.embedder_type import EmbedderType
from app.domain.constants.text_cleaner_type import TextCleanerType
from app.domain.constants.text_splitter_type import TextSplitterType

logger = logging.getLogger(__name__)


@dataclass(
    frozen=True,
    kw_only=True
)
class DocumentIngestionServiceConfiguration:
    MIN_SPLIT_SIZE: Final[int] = 1
    MAX_SPLIT_SIZE: Final[int] = 100_000

    MIN_SPLIT_OVERLAP: Final[int] = 0

    DEFAULT_SPLIT_SIZE: Final[int] = 1000
    DEFAULT_SPLIT_OVERLAP: Final[int] = 200
    DEFAULT_TEXT_CLEANER_TYPE: Final[TextCleanerType] = TextCleanerType.SPACE
    DEFAULT_TEXT_SPLITTER_TYPE: Final[TextSplitterType] = TextSplitterType.RECURSIVE
    DEFAULT_EMBEDDER_TYPE: Final[EmbedderType] = EmbedderType.OLLAMA

    ALLOWED_TEXT_CLEANER_TYPES = {
        e.value for e in TextCleanerType
    }
    ALLOWED_TEXT_SPLITTER_TYPES = {
        e.value for e in TextSplitterType
    }
    ALLOWED_EMBEDDER_TYPES = {
        e.value for e in EmbedderType
    }

    text_cleaner_type: TextCleanerType = DEFAULT_TEXT_CLEANER_TYPE
    text_splitter_type: TextSplitterType = DEFAULT_TEXT_SPLITTER_TYPE
    embedder_type: EmbedderType = DEFAULT_EMBEDDER_TYPE
    split_size: int = DEFAULT_SPLIT_SIZE
    split_overlap: int = DEFAULT_SPLIT_OVERLAP

    def __post_init__(
            self
    ) -> None:
        try:
            self._validate_all()
            logger.info("DocumentProcessingConfiguration initialized successfully")
        except ValueError as e:
            logger.error(
                "DocumentProcessingConfiguration validation failed",
                extra={
                    "error": str(e)
                },
                exc_info=True
            )
            raise

    def _validate_all(
            self
    ) -> None:
        self._validate_split_size()
        self._validate_split_overlap()
        self._validate_text_cleaner_type()
        self._validate_text_splitter_type()
        self._validate_embedder_type()

    def _validate_split_size(
            self
    ) -> None:
        if not (self.MIN_SPLIT_SIZE
                <= self.split_size
                <= self.MAX_SPLIT_SIZE):
            raise ValueError(
                f"split_size debe estar entre {self.MIN_SPLIT_SIZE} y {self.MAX_SPLIT_SIZE}, "
                f"se recibió: {self.split_size}"
            )

    def _validate_split_overlap(
            self
    ) -> None:
        if self.split_overlap < self.MIN_SPLIT_OVERLAP:
            raise ValueError(
                f"split_overlap no puede ser negativo, se recibió: {self.split_overlap}"
            )
        if self.split_overlap >= self.split_size:
            raise ValueError(
                f"split_overlap ({self.split_overlap}) debe ser menor que split_size ({self.split_size})"
            )

    def _validate_text_cleaner_type(
            self
    ) -> None:
        self._validate_non_empty_string("text_cleaner_type", self.text_cleaner_type)

        if self.text_cleaner_type not in self.ALLOWED_TEXT_CLEANER_TYPES:
            raise ValidationError(
                f"text_cleaner_type no soportado: '{self.text_cleaner_type}'. "
                f"Valores permitidos: {', '.join(sorted(self.ALLOWED_TEXT_CLEANER_TYPES))}",
                status_code=400
            )

    def _validate_text_splitter_type(
            self
    ) -> None:
        self._validate_non_empty_string("text_splitter_type", self.text_splitter_type)

        if self.text_splitter_type not in self.ALLOWED_TEXT_SPLITTER_TYPES:
            raise ValidationError(
                f"text_splitter_type no soportado: '{self.text_splitter_type}'. "
                f"Valores permitidos: {', '.join(sorted(self.ALLOWED_TEXT_SPLITTER_TYPES))}",
                status_code=400
            )

    def _validate_embedder_type(
            self
    ) -> None:
        self._validate_non_empty_string("embedder_type", self.embedder_type)

        if self.embedder_type not in self.ALLOWED_EMBEDDER_TYPES:
            raise ValidationError(
                f"embedder_type no soportado: '{self.embedder_type}'. "
                f"Valores permitidos: {', '.join(sorted(self.ALLOWED_EMBEDDER_TYPES))}",
                status_code=400
            )

    @staticmethod
    def _validate_non_empty_string(
            field_name: str,
            value: str
    ) -> None:
        if not value or not isinstance(value, str) or not value.strip():
            logger.warning(
                "Validation failed: empty or invalid string"
            )
            raise ValidationError(
                f"{field_name} no puede estar vacío",
                status_code=400
            )
