import logging
from dataclasses import dataclass
from typing import Final

from app.application.exceptions.app_exception import ValidationError
from app.domain.constants.embedder_type import EmbedderType

logger = logging.getLogger(__name__)


@dataclass(
    frozen=True,
    kw_only=True
)
class DocumentContextServiceConfiguration:
    DEFAULT_EMBEDDER_TYPE: Final[EmbedderType] = EmbedderType.OLLAMA

    ALLOWED_EMBEDDER_TYPES = {
        e.value for e in EmbedderType
    }

    embedder_type: EmbedderType = DEFAULT_EMBEDDER_TYPE

    def __post_init__(
            self
    ) -> None:
        try:
            self._validate_all()
            logger.info("DocumentContextServiceConfiguration initialized successfully")
        except ValueError as e:
            logger.error(
                "DocumentContextServiceConfiguration validation failed",
                extra={
                    "error": str(e)
                },
                exc_info=True
            )
            raise

    def _validate_all(
            self
    ) -> None:
        self._validate_embedder_type()

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
