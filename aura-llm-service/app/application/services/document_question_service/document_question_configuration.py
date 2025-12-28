from dataclasses import dataclass
from typing import Optional

from app.application.exceptions.app_exceptions import ValidationError


@dataclass(frozen=True)
class DocumentQuestionConfiguration:
    max_fragments: int = 3
    max_question_length: int = 1000
    max_history_count: int = 3
    system_prompt: Optional[str] = None

    MIN_QUESTION_LENGTH: int = 1
    MIN_MAX_QUESTION_LENGTH: int = 1
    MAX_MAX_QUESTION_LENGTH: int = 10000

    MIN_HISTORY_COUNT: int = 1
    MAX_HISTORY_COUNT: int = 6

    DEFAULT_SYSTEM_PROMPT: str = (
        "Eres un asistente útil que responde únicamente basándose en el contexto proporcionado. "
        "La respuesta debe estar en formato Markdown e incluir títulos (`#`), subtítulos (`##`), "
        "listas (`-`), negritas (`**`) y tablas cuando corresponda. "
        "Si el contexto no contiene suficiente información, indica claramente que la información "
        "no está disponible y ofrece una respuesta general relacionada al tema sin inventar datos."
    )

    def __post_init__(self):
        self._validate()

    def _validate(self) -> None:
        self._validate_max_question_length()
        self._validate_max_history_count()

    def _validate_max_question_length(self) -> None:
        if not (self.MIN_MAX_QUESTION_LENGTH <= self.max_question_length <= self.MAX_MAX_QUESTION_LENGTH):
            raise ValidationError(
                f"max_question_length must be between {self.MIN_MAX_QUESTION_LENGTH} "
                f"and {self.MAX_MAX_QUESTION_LENGTH}",
                status_code=500
            )

    def _validate_max_history_count(self) -> None:
        if not (self.MIN_HISTORY_COUNT <= self.max_history_count <= self.MAX_HISTORY_COUNT):
            raise ValidationError(
                f"max_history_count must be between {self.MIN_HISTORY_COUNT} "
                f"and {self.MAX_HISTORY_COUNT}",
                status_code=500
            )

    @property
    def effective_system_prompt(self) -> str:
        return self.system_prompt or self.DEFAULT_SYSTEM_PROMPT

