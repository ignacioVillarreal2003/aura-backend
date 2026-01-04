import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DocumentQuestionConfiguration:
    fragments_count: int = 3
    question_length: int = 1000
    history_count: int = 5
    custom_system_prompt: Optional[str] = None

    min_fragments_count: int = field(
        default=1,
        repr=False
    )
    max_fragments_count: int = field(
        default=10,
        repr=False
    )

    min_question_length: int = field(
        default=1,
        repr=False
    )
    max_question_length: int = field(
        default=10000,
        repr=False
    )

    min_history_count: int = field(
        default=0,
        repr=False
    )
    max_history_count: int = field(
        default=10,
        repr=False
    )

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
                "fragments_count": self.fragments_count,
                "question_length": self.question_length,
                "history_count": self.history_count,
                "has_custom_prompt": self.custom_system_prompt is not None
            }
        )

    def _validate(self) -> None:
        self._validate_fragments()
        self._validate_question_length()
        self._validate_history()

    def _validate_fragments(self) -> None:
        if not self.min_fragments_count <= self.fragments_count <= self.max_fragments_count:
            raise ValueError(
                "La cantidad de fragmentos no es válida. "
                f"Debe estar entre {self.min_fragments_count} y {self.max_fragments_count}."
            )

    def _validate_question_length(self) -> None:
        if not self.min_question_length <= self.question_length <= self.max_question_length:
            raise ValueError(
                "La longitud de la pregunta no es válida. "
                f"Debe estar entre {self.min_question_length} y {self.max_question_length} caracteres."
            )

    def _validate_history(self) -> None:
        if not self.min_history_count <= self.history_count <= self.max_history_count:
            raise ValueError(
                "La cantidad de mensajes de historial no es válida. "
                f"Debe estar entre {self.min_history_count} y {self.max_history_count}."
            )

    @property
    def system_prompt(self) -> str:
        return self.custom_system_prompt or self.default_system_prompt
