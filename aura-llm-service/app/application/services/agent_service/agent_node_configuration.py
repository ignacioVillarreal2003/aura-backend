import logging
from dataclasses import dataclass
from typing import Dict, Optional

from app.domain.constants.sentimient import Sentiment

logger = logging.getLogger(__name__)


@dataclass(
    frozen=True,
    kw_only=True
)
class AgentNodeConfiguration:
    custom_system_prompt: Optional[str] = None
    custom_sentiment_instructions: Optional[Dict[Sentiment, str]] = None

    def __post_init__(self) -> None:
        self._validate_all()
        logger.debug("AgentNodeConfiguration initialized")

    def _validate_all(self) -> None:
        for sentiment in Sentiment:
            if sentiment not in self.sentiment_instructions:
                raise ValueError(f"Falta instrucción de sentimiento para: {sentiment.value}")

    def get_sentiment_instruction(self, sentiment: Sentiment) -> str:
        return self.sentiment_instructions.get(
            sentiment,
            self.sentiment_instructions[Sentiment.neutral]
        )

    @property
    def system_prompt(self) -> str:
        return self.custom_system_prompt or self._get_default_system_prompt()

    @property
    def sentiment_instructions(self) -> Dict[Sentiment, str]:
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
            Sentiment.positive: (
                "El usuario está contento y tiene una actitud positiva. "
                "Usa un tono amigable, optimista y emojis apropiados cuando sea natural. 😊"
            ),
            Sentiment.neutral: (
                "El usuario tiene un tono neutral y profesional. "
                "Mantén un tono cortés, claro y directo sin ser demasiado formal."
            ),
            Sentiment.negative: (
                "El usuario está frustrado, molesto o insatisfecho. "
                "Sé empático, paciente y profesional. Evita emojis. "
                "Enfócate en resolver su problema de manera efectiva."
            )
        }
