import logging
from dataclasses import dataclass
from typing import Dict, Optional, Final, Tuple

from app.application.services.agent_service.constants.sentimient import Sentiment

logger = logging.getLogger(__name__)


@dataclass(
    frozen=True,
    kw_only=True
)
class AgentNodeConfiguration:
    MAX_CUSTOM_SYSTEM_PROMPT_LENGTH: Final[Tuple[int, int]] = (1_000, 10_000)
    MAX_CUSTOM_SENTIMENT_INSTRUCTIONS_LENGTH: Final[Tuple[int, int]] = (1_000, 10_000)

    DEFAULT_CUSTOM_SYSTEM_PROMPT_LENGTH: Final[Tuple[int, int]] = (1, 1_000)
    DEFAULT_CUSTOM_SENTIMENT_INSTRUCTIONS_LENGTH: Final[Tuple[int, int]] = (1, 1_000)

    custom_system_prompt_length: Final[Tuple[int, int]] = DEFAULT_CUSTOM_SYSTEM_PROMPT_LENGTH
    custom_sentiment_instructions_length: int = DEFAULT_CUSTOM_SENTIMENT_INSTRUCTIONS_LENGTH

    custom_system_prompt: Optional[str] = None
    custom_sentiment_instructions: Optional[Dict[Sentiment, str]] = None

    @property
    def system_prompt(
            self
    ) -> str:
        return self.custom_system_prompt or self._get_default_system_prompt()

    @property
    def sentiment_instructions(
            self
    ) -> Dict[Sentiment, str]:
        return self.custom_sentiment_instructions or self._get_default_sentiment_instructions()

    @staticmethod
    def _get_default_system_prompt() -> str:
        return (
            "Eres un asistente inteligente y útil. "
            "Tienes acceso a herramientas para responder preguntas sobre documentos. "
            "Usa las herramientas cuando sea necesario para proporcionar respuestas precisas."
        )

    @staticmethod
    def _get_default_sentiment_instructions() -> Dict[Sentiment, str]:
        return {
            Sentiment.POSITIVE: (
                "El usuario está contento y tiene una actitud positiva. "
                "Usa un tono amigable, optimista y emojis apropiados cuando sea natural. 😊"
            ),
            Sentiment.NEUTRAL: (
                "El usuario tiene un tono neutral y profesional. "
                "Mantén un tono cortés, claro y directo sin ser demasiado formal."
            ),
            Sentiment.NEGATIVE: (
                "El usuario está frustrado, molesto o insatisfecho. "
                "Sé empático, paciente y profesional. Evita emojis. "
                "Enfócate en resolver su problema de manera efectiva."
            )
        }

    def __post_init__(
            self
    ) -> None:
        try:
            self._validate_all()
            logger.debug("AgentNodeConfiguration initialized")
        except ValueError as e:
            logger.error(
                "Configuration validation failed",
                extra={
                    "error": str(e)
                },
                exc_info=True
            )
            raise

    def _validate_all(
            self
    ) -> None:
        logger.debug(
            "Validating AgentNodeConfiguration",
            extra={
                "has_custom_system_prompt": self.custom_system_prompt is not None,
                "has_custom_sentiment_instructions": self.custom_sentiment_instructions is not None
            }
        )

        if self.custom_system_prompt is not None:
            self._validate_custom_system_prompt()
        if self.custom_sentiment_instructions is not None:
            self._validate_custom_sentiment_instructions()

    def _validate_custom_system_prompt(
            self
    ):
        logger.debug(
            "Validating custom system prompt",
            extra={
                "custom_system_prompt": self.custom_system_prompt
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

        if len(self.custom_system_prompt) > self.MAX_CUSTOM_SYSTEM_PROMPT_LENGTH[1]:
            logger.error("Custom system prompt validation failed: prompt too long")
            raise ValueError(
                f"El prompt del sistema es demasiado largo. El máximo permitido es de {self.MAX_CUSTOM_SYSTEM_PROMPT_LENGTH[1]} caracteres."
            )

    def _validate_custom_sentiment_instructions(
            self
    ) -> None:
        logger.debug(
            "Validating custom sentiment instructions",
            extra={
                "custom_sentiment_instructions": self.custom_sentiment_instructions
            }
        )

        if not isinstance(self.custom_sentiment_instructions, dict):
            logger.error(
                "Custom sentiment instructions validation failed: invalid type",
                extra={
                    "type": type(self.custom_sentiment_instructions).__name__
                }
            )
            raise ValueError("Las instrucciones de sentimiento deben ser un diccionario.")

        for sentiment in Sentiment:
            if sentiment not in self.custom_sentiment_instructions:
                logger.error(
                    "Custom sentiment instructions validation failed: missing sentiment",
                    extra={
                        "missing_sentiment": sentiment.value
                    }
                )
                raise ValueError(f"Falta la instrucción para el sentimiento: {sentiment.value}.")

        for sentiment, instruction in self.custom_sentiment_instructions.items():
            logger.debug(
                "Validating sentiment instruction",
                extra={
                    "sentiment": sentiment.value
                }
            )

            if not isinstance(sentiment, Sentiment):
                logger.error(
                    "Invalid sentiment key type in custom sentiment instructions",
                    extra={
                        "key_type": type(sentiment).__name__
                    }
                )
                raise ValueError("Las claves de las instrucciones de sentimiento deben ser valores de Sentiment.")

            if not isinstance(instruction, str):
                logger.error(
                    "Invalid sentiment instruction type",
                    extra={
                        "sentiment": sentiment.value,
                        "instruction_type": type(instruction).__name__
                    }
                )
                raise ValueError(f"La instrucción para el sentimiento {sentiment.value} debe ser una cadena de texto.")

            if not instruction.strip():
                logger.error(
                    "Empty or whitespace-only sentiment instruction",
                    extra={
                        "sentiment": sentiment.value
                    }
                )
                raise ValueError(f"La instrucción para el sentimiento {sentiment.value} no puede estar vacía.")

            if len(instruction) > self.MAX_CUSTOM_SENTIMENT_INSTRUCTIONS_LENGTH[1]:
                logger.error("Sentiment instruction too long")
                raise ValueError(
                    f"La instrucción para el sentimiento {sentiment.value} es demasiado larga. "
                    f"El máximo permitido es de {self.MAX_CUSTOM_SENTIMENT_INSTRUCTIONS_LENGTH[1]} caracteres."
                )

    def get_sentiment_instruction(
            self,
            sentiment: Sentiment
    ) -> str:
        return self.sentiment_instructions.get(
            sentiment,
            self.sentiment_instructions[Sentiment.NEUTRAL]
        )
