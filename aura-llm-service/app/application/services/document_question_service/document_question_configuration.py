import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DocumentQuestionConfiguration:
    max_context_fragments_count: int = 3
    CONFIG_MIN_MAX_CONTEXT_FRAGMENTS_COUNT: int = field(default=1, repr=False)
    CONFIG_MAX_MAX_CONTEXT_FRAGMENTS_COUNT: int = field(default=6, repr=False)

    min_question_length: int = 1
    max_question_length: int = 1000
    CONFIG_MIN_MAX_QUESTION_LENGTH: int = field(default=100, repr=False)
    CONFIG_MAX_MAX_QUESTION_LENGTH: int = field(default=10000, repr=False)

    max_history_messages_count: int = 3
    CONFIG_MIN_MAX_HISTORY_MESSAGES_COUNT: int = field(default=0, repr=False)
    CONFIG_MAX_MAX_HISTORY_MESSAGES_COUNT: int = field(default=6, repr=False)

    custom_system_prompt: Optional[str] = None
    default_system_prompt: str = field(
        default=(
            "Eres un asistente especializado en responder preguntas basándote únicamente en el contexto proporcionado. "
            "REGLAS ESTRICTAS:\n"
            "1. Responde SOLO con información del contexto provisto\n"
            "2. Si la información no está en el contexto, indica claramente que no está disponible\n"
            "3. NO inventes ni asumas información que no esté explícita\n"
            "4. Usa formato Markdown: títulos (#, ##), listas (-), negritas (**), tablas cuando corresponda\n"
            "5. Sé conciso pero completo en tus respuestas\n"),
        repr=False
    )

    def __post_init__(self) -> None:
        self._validate()
        logger.info(
            "DocumentQuestionConfiguration initialized",
            extra={
                "max_context_fragments": self.max_context_fragments_count,
                "min_question_length": self.min_question_length,
                "max_question_length": self.max_question_length,
                "max_history_messages": self.max_history_messages_count,
                "system_prompt": self.custom_system_prompt
                if self.custom_system_prompt is not None
                else self.default_system_prompt
            }
        )

    def _validate(self) -> None:
        self._validate_max_context_fragments_count()
        self._validate_max_question_length()
        self._validate_max_history_messages_count()

    def _validate_max_context_fragments_count(self) -> None:
        if not (self.CONFIG_MIN_MAX_CONTEXT_FRAGMENTS_COUNT
                <= self.max_context_fragments_count
                <= self.CONFIG_MAX_MAX_CONTEXT_FRAGMENTS_COUNT):
            raise ValueError(
                "La cantidad de fragmentos máxima no es válida."
                f"Debe estar entre {self.CONFIG_MIN_MAX_CONTEXT_FRAGMENTS_COUNT} y {self.CONFIG_MAX_MAX_CONTEXT_FRAGMENTS_COUNT}."
            )

    def _validate_max_question_length(self) -> None:
        if not (self.CONFIG_MIN_MAX_QUESTION_LENGTH
                <= self.max_question_length
                <= self.CONFIG_MAX_MAX_QUESTION_LENGTH):
            raise ValueError(
                "La longitud máxima de la pregunta no es válida."
                f"Debe estar entre {self.CONFIG_MIN_MAX_QUESTION_LENGTH} y {self.CONFIG_MAX_MAX_QUESTION_LENGTH} caracteres."
            )

    def _validate_max_history_messages_count(self) -> None:
        if not (self.CONFIG_MIN_MAX_HISTORY_MESSAGES_COUNT
                <= self.max_history_messages_count
                <= self.CONFIG_MAX_MAX_HISTORY_MESSAGES_COUNT):
            raise ValueError(
                "La cantidad de mensajes de historial máxima no es válida."
                f"Debe estar entre {self.CONFIG_MIN_MAX_HISTORY_MESSAGES_COUNT} y {self.CONFIG_MAX_MAX_HISTORY_MESSAGES_COUNT}."
            )

    @property
    def system_prompt(self) -> str:
        return self.custom_system_prompt or self.default_system_prompt
