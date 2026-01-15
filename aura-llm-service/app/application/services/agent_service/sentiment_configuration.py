import logging
from dataclasses import dataclass
from typing import Final, Optional


logger = logging.getLogger(__name__)


@dataclass(
    frozen=True,
    kw_only=True
)
class SentimentConfiguration:
    custom_system_prompt: Optional[str] = None
    custom_user_template: Optional[str] = None

    @property
    def system_prompt(self) -> str:
        return self.custom_system_prompt or self._get_default_system_prompt()

    @property
    def user_template(self) -> str:
        return self.custom_user_template or self._get_default_user_template()

    @staticmethod
    def _get_default_system_prompt() -> str:
        return (
            "Eres un experto clasificador de sentimientos. "
            "Tu tarea es analizar el mensaje del usuario y clasificar su sentimiento emocional. "
            "Debes responder ÚNICAMENTE con una de estas tres palabras: positive, negative, neutral. "
            "No incluyas explicaciones, puntuación adicional ni texto extra."
        )

    @staticmethod
    def _get_default_user_template() -> str:
        return (
            "Analiza el siguiente mensaje y clasifica su sentimiento:\n\n"
            '"{message}"'
        )

    def __post_init__(self) -> None:
        self._validate_all()
        logger.debug("SentimentConfiguration initialized")

    def _validate_all(self) -> None:
        if "{message}" not in self.user_template:
            raise ValueError("user_template debe contener el placeholder {message}")