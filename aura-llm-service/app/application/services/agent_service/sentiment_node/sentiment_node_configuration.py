import logging
from dataclasses import dataclass
from typing import Optional, Final, Tuple

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class SentimentNodeConfiguration:
    MAX_CUSTOM_SYSTEM_PROMPT_LENGTH: Final[Tuple[int, int]] = (1_000, 10_000)

    DEFAULT_CUSTOM_SYSTEM_PROMPT_LENGTH: Final[Tuple[int, int]] = (1, 1_000)

    custom_system_prompt_length: Final[Tuple[int, int]] = DEFAULT_CUSTOM_SYSTEM_PROMPT_LENGTH

    custom_system_prompt: Optional[str] = None

    @property
    def system_prompt(self) -> str:
        return self.custom_system_prompt or self._get_default_system_prompt()

    @staticmethod
    def _get_default_system_prompt() -> str:
        return (
            "Eres un experto clasificador de sentimientos. "
            "Tu tarea es analizar el mensaje del usuario y clasificar su sentimiento emocional. "
            "Debes responder ÚNICAMENTE con una de estas tres palabras: POSITIVE, NEGATIVE, NEUTRAL. "
            "No incluyas explicaciones, puntuación adicional ni texto extra."
        )

    def __post_init__(self) -> None:
        try:
            self._validate_all()
            logger.debug("SentimentNodeConfiguration initialized")
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
        logger.debug(
            "Validating SentimentNodeConfiguration",
            extra={
                "has_custom_system_prompt": self.custom_system_prompt is not None
            }
        )

        if self.custom_system_prompt is not None:
            self._validate_custom_system_prompt()

    def _validate_custom_system_prompt(self) -> None:
        logger.debug(
            "Validating custom system prompt",
            extra={
                "prompt_length": len(self.custom_system_prompt) if self.custom_system_prompt else 0
            }
        )

        if not isinstance(self.custom_system_prompt, str):
            logger.error(
                "Custom system prompt validation failed: invalid type",
                extra={
                    "type": type(self.custom_system_prompt).__name__
                }
            )
            raise ValueError("El prompt del sistema debe ser una cadena de texto.")

        if not self.custom_system_prompt.strip():
            logger.error("Custom system prompt validation failed: empty or whitespace-only")
            raise ValueError("El prompt del sistema no puede estar vacío ni contener solo espacios en blanco.")

        if len(self.custom_system_prompt) > self.max_custom_system_prompt_length:
            logger.error(
                "Custom system prompt validation failed: prompt too long",
                extra={
                    "length": len(self.custom_system_prompt),
                    "max_length": self.max_custom_system_prompt_length
                }
            )
            raise ValueError(f"El prompt del sistema es demasiado largo. El máximo permitido es de {self.max_custom_system_prompt_length} caracteres.")
