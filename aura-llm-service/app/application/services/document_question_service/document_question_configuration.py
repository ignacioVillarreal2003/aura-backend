import logging
from dataclasses import dataclass
from typing import Optional

from app.application.exceptions.app_exceptions import ValidationError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DocumentQuestionConfiguration:
    default_fragments_count: int = 3
    default_question_length: int = 1000
    default_history_count: int = 3
    default_system_prompt: Optional[str] = None

    MIN_QUESTION_LENGTH: int = 1
    MAX_QUESTION_LENGTH: int = 10000

    MIN_HISTORY_COUNT: int = 1
    MAX_HISTORY_COUNT: int = 6

    SYSTEM_PROMPT: str = (
        "Eres un asistente útil que responde únicamente basándose en el contexto proporcionado. "
        "La respuesta debe estar en formato Markdown e incluir títulos (`#`), subtítulos (`##`), "
        "listas (`-`), negritas (`**`) y tablas cuando corresponda. "
        "Si el contexto no contiene suficiente información, indica claramente que la información "
        "no está disponible y ofrece una respuesta general relacionada al tema sin inventar datos."
    )

    def __post_init__(self):
        logger.debug(
            "Initializing DocumentQuestionConfiguration",
            extra={
                "default_fragments_count": self.default_fragments_count,
                "default_question_length": self.default_question_length,
                "default_history_count": self.default_history_count
            }
        )
        self._validate()
        logger.info(
            "DocumentQuestionConfiguration initialized successfully",
            extra={
                "default_fragments_count": self.default_fragments_count,
                "default_question_length": self.default_question_length,
                "default_history_count": self.default_history_count
            }
        )

    def _validate(self) -> None:
        self._validate_question_length()
        self._validate_history_count()

    def _validate_question_length(self) -> None:
        logger.debug(
            "Validating question length configuration",
            extra={
                "default_question_length": self.default_question_length,
                "min_question_length": self.MIN_QUESTION_LENGTH,
                "max_question_length": self.MAX_QUESTION_LENGTH
            }
        )
        if not (self.MIN_QUESTION_LENGTH <= self.default_question_length <= self.MAX_QUESTION_LENGTH):
            logger.error(
                "Invalid question length configuration",
                extra={
                    "default_question_length": self.default_question_length,
                    "min_question_length": self.MIN_QUESTION_LENGTH,
                    "max_question_length": self.MAX_QUESTION_LENGTH
                }
            )
            raise ValidationError(
                f"Question length must be between {self.MIN_QUESTION_LENGTH} and {self.MAX_QUESTION_LENGTH}",
                status_code=500
            )

    def _validate_history_count(self) -> None:
        logger.debug(
            "Validating history count configuration",
            extra={
                "default_history_count": self.default_history_count,
                "min_history_count": self.MIN_HISTORY_COUNT,
                "max_history_count": self.MAX_HISTORY_COUNT
            }
        )
        if not (self.MIN_HISTORY_COUNT <= self.default_history_count <= self.MAX_HISTORY_COUNT):
            logger.error(
                "Invalid history count configuration",
                extra={
                    "default_history_count": self.default_history_count,
                    "min_history_count": self.MIN_HISTORY_COUNT,
                    "max_history_count": self.MAX_HISTORY_COUNT
                }
            )
            raise ValidationError(
                f"History count must be between {self.MIN_HISTORY_COUNT} and {self.MAX_HISTORY_COUNT}",
                status_code=500
            )

    @property
    def system_prompt(self) -> str:
        return self.default_system_prompt or self.SYSTEM_PROMPT
