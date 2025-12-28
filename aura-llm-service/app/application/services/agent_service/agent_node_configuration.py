from dataclasses import dataclass
from typing import Dict

from app.domain.constants.sentimient import Sentiment


@dataclass(frozen=True)
class AgentNodeConfig:
    base_system_prompt: str = "Eres un asistente inteligente orquestador."

    sentiment_instructions: Dict[Sentiment, str] = None

    def __post_init__(self):
        if self.sentiment_instructions is None:
            object.__setattr__(self, 'sentiment_instructions', {
                Sentiment.positive: (
                    "El usuario está contento. Usa un tono amigable y emojis apropiados. 😊"
                ),
                Sentiment.neutral: (
                    "El usuario tiene un tono neutral. Mantén un tono profesional y amigable."
                ),
                Sentiment.negative: (
                    "El usuario está enojado o frustrado. Sé empático, formal y comprensivo."
                )
            })