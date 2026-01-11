import logging
from dataclasses import dataclass
from typing import Final, Optional

logger = logging.getLogger(__name__)


@dataclass(
    frozen=True,
    kw_only=True
)
class DocumentQuestionConfiguration:
    MIN_CONTEXT_FRAGMENTS_COUNT: Final[int] = 1
    MAX_CONTEXT_FRAGMENTS_COUNT: Final[int] = 6

    MIN_QUESTION_LENGTH: Final[int] = 100
    MAX_QUESTION_LENGTH: Final[int] = 10000

    MIN_HISTORY_MESSAGES_COUNT: Final[int] = 0
    MAX_HISTORY_MESSAGES_COUNT: Final[int] = 6

    DEFAULT_MAX_CONTEXT_FRAGMENTS_COUNT: Final[int] = 3
    DEFAULT_MIN_QUESTION_LENGTH: Final[int] = 1
    DEFAULT_MAX_QUESTION_LENGTH: Final[int] = 1000
    DEFAULT_MAX_HISTORY_MESSAGES_COUNT: Final[int] = 3

    max_context_fragments_count: int = DEFAULT_MAX_CONTEXT_FRAGMENTS_COUNT
    min_question_length: int = DEFAULT_MIN_QUESTION_LENGTH
    max_question_length: int = DEFAULT_MAX_QUESTION_LENGTH
    max_history_messages_count: int = DEFAULT_MAX_HISTORY_MESSAGES_COUNT
    custom_system_prompt: Optional[str] = None

    def __post_init__(self) -> None:
        try:
            self._validate_all()
            logger.info(
                "DocumentQuestionConfiguration initialized successfully",
                extra={
                    "max_context_fragments_count": self.max_context_fragments_count,
                    "min_question_length": self.min_question_length,
                    "max_question_length": self.max_question_length,
                    "max_history_messages_count": self.max_history_messages_count,
                    "uses_custom_system_prompt": self.custom_system_prompt is not None
                }
            )
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
        self._validate_max_context_fragments_count()
        self._validate_max_question_length()
        self._validate_max_history_messages_count()

    def _validate_max_context_fragments_count(self) -> None:
        if not (self.MIN_CONTEXT_FRAGMENTS_COUNT
                <= self.max_context_fragments_count
                <= self.MAX_CONTEXT_FRAGMENTS_COUNT):
            raise ValueError(
                f"max_context_fragments_count debe estar entre {self.MIN_CONTEXT_FRAGMENTS_COUNT} y {self.MAX_CONTEXT_FRAGMENTS_COUNT}, "
                f"se recibió: {self.max_context_fragments_count}"
            )

    def _validate_max_question_length(self) -> None:
        if not (self.MIN_QUESTION_LENGTH
                <= self.max_question_length
                <= self.MAX_QUESTION_LENGTH):
            raise ValueError(
                f"max_question_length debe estar entre {self.MIN_QUESTION_LENGTH} y {self.MAX_QUESTION_LENGTH}, "
                f"se recibió: {self.max_question_length}"
            )

        if self.min_question_length < 0:
            raise ValueError(
                f"min_question_length no puede ser negativo, se recibió: {self.min_question_length}"
            )

        if self.min_question_length > self.max_question_length:
            raise ValueError(
                f"min_question_length ({self.min_question_length}) no puede ser mayor que "
                f"max_question_length ({self.max_question_length})"
            )

    def _validate_max_history_messages_count(self) -> None:
        if not (self.MIN_HISTORY_MESSAGES_COUNT
                <= self.max_history_messages_count
                <= self.MAX_HISTORY_MESSAGES_COUNT):
            raise ValueError(
                f"max_history_messages_count debe estar entre {self.MIN_HISTORY_MESSAGES_COUNT} y {self.MAX_HISTORY_MESSAGES_COUNT}, "
                f"se recibió: {self.max_history_messages_count}"
            )

    @property
    def system_prompt(self) -> str:
        return self.custom_system_prompt or self._get_default_system_prompt()

    @staticmethod
    def _get_default_system_prompt() -> str:
        return (
            "Eres un asistente especializado en responder preguntas basándote únicamente en el contexto proporcionado. "
            "REGLAS ESTRICTAS:\n"
            "1. Responde SOLO con información del contexto provisto\n"
            "2. Si la información no está en el contexto, indica claramente que no está disponible\n"
            "3. NO inventes ni asumas información que no esté explícita\n"
            "4. Usa formato Markdown: títulos (#, ##), listas (-), negritas (**), tablas cuando corresponda\n"
            "5. Sé conciso pero completo en tus respuestas\n"
        )
