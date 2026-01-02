from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class DocumentQuestionConfiguration:
    default_fragments_count: int = 3
    default_question_length: int = 1000
    default_history_count: int = 3
    default_system_prompt: Optional[str] = None

    min_fragments_count: int = 1
    max_fragments_count: int = 6

    min_question_length: int = 1
    max_question_length: int = 10000

    min_history_count: int = 1
    max_history_count: int = 6

    system_prompt: str = (
        "Eres un asistente útil que responde únicamente basándose en el contexto proporcionado. "
        "La respuesta debe estar en formato Markdown e incluir títulos (`#`), subtítulos (`##`), "
        "listas (`-`), negritas (`**`) y tablas cuando corresponda. "
        "Si el contexto no contiene suficiente información, indica claramente que la información "
        "no está disponible y ofrece una respuesta general relacionada al tema sin inventar datos."
    )

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        self._validate_fragments_count()
        self._validate_question_length()
        self._validate_history_count()

    def _validate_fragments_count(self) -> None:
        if not (self.min_fragments_count <= self.default_fragments_count <= self.max_fragments_count):
            raise ValueError(
                f"default_fragments_count must be between {self.min_fragments_count} and "
                f"{self.max_fragments_count}, got {self.default_fragments_count}"
            )

    def _validate_question_length(self) -> None:
        if not (self.min_question_length <= self.default_question_length <= self.max_question_length):
            raise ValueError(
                f"default_question_length must be between {self.min_question_length} and "
                f"{self.max_question_length}, got {self.default_question_length}"
            )

    def _validate_history_count(self) -> None:
        if not (self.min_history_count <= self.default_history_count <= self.max_history_count):
            raise ValueError(
                f"default_history_count must be between {self.min_history_count} and "
                f"{self.max_history_count}, got {self.default_history_count}"
            )

    @property
    def get_system_prompt(self) -> str:
        return self.default_system_prompt or self.system_prompt
