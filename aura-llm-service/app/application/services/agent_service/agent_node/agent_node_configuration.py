import logging
from dataclasses import dataclass
from typing import Dict, Final, Optional, Tuple

from app.application.services.agent_service.constants.sentimient import Sentiment

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class AgentNodeConfiguration:
    MAX_CUSTOM_SYSTEM_PROMPT_LENGTH: Final[Tuple[int, int]] = (1_000, 10_000)
    MAX_CUSTOM_SENTIMENT_INSTRUCTIONS_LENGTH: Final[Tuple[int, int]] = (1_000, 10_000)

    DEFAULT_CUSTOM_SYSTEM_PROMPT_LENGTH: Final[Tuple[int, int]] = (1, 1_000)
    DEFAULT_CUSTOM_SENTIMENT_INSTRUCTIONS_LENGTH: Final[Tuple[int, int]] = (1, 1_000)

    custom_system_prompt_length: Final[Tuple[int, int]] = DEFAULT_CUSTOM_SYSTEM_PROMPT_LENGTH
    custom_sentiment_instructions_length: Final[Tuple[int, int]] = DEFAULT_CUSTOM_SENTIMENT_INSTRUCTIONS_LENGTH

    custom_system_prompt: Optional[str] = None
    custom_sentiment_instructions: Optional[Dict[Sentiment, str]] = None

    def __post_init__(self) -> None:
        try:
            self._validate_all()
            logger.debug("AgentNodeConfiguration initialized")
        except ValueError as e:
            logger.error(
                "AgentNodeConfiguration validation failed",
                extra={"error": str(e)},
                exc_info=True
            )
            raise

    def _validate_all(self) -> None:
        if self.custom_system_prompt is not None:
            self._validate_custom_system_prompt()
        if self.custom_sentiment_instructions is not None:
            self._validate_custom_sentiment_instructions()

    def _validate_custom_system_prompt(self) -> None:
        if not isinstance(self.custom_system_prompt, str):
            raise ValueError(
                f"custom_system_prompt must be a string, got: {type(self.custom_system_prompt).__name__}"
            )
        if not self.custom_system_prompt.strip():
            raise ValueError("custom_system_prompt cannot be empty or whitespace-only")
        if len(self.custom_system_prompt) > self.MAX_CUSTOM_SYSTEM_PROMPT_LENGTH[1]:
            raise ValueError(
                f"custom_system_prompt is too long. "
                f"Maximum: {self.MAX_CUSTOM_SYSTEM_PROMPT_LENGTH[1]} characters."
            )

    def _validate_custom_sentiment_instructions(self) -> None:
        if not isinstance(self.custom_sentiment_instructions, dict):
            raise ValueError(
                f"custom_sentiment_instructions must be a dict, "
                f"got: {type(self.custom_sentiment_instructions).__name__}"
            )

        for sentiment in Sentiment:
            if sentiment not in self.custom_sentiment_instructions:
                raise ValueError(
                    f"Missing sentiment instruction for: {sentiment.value}"
                )

        for sentiment, instruction in self.custom_sentiment_instructions.items():
            if not isinstance(sentiment, Sentiment):
                raise ValueError(
                    f"Sentiment keys must be Sentiment instances, got: {type(sentiment).__name__}"
                )
            if not isinstance(instruction, str):
                raise ValueError(
                    f"Instruction for sentiment '{sentiment.value}' must be a string, "
                    f"got: {type(instruction).__name__}"
                )
            if not instruction.strip():
                raise ValueError(
                    f"Instruction for sentiment '{sentiment.value}' cannot be empty"
                )
            if len(instruction) > self.MAX_CUSTOM_SENTIMENT_INSTRUCTIONS_LENGTH[1]:
                raise ValueError(
                    f"Instruction for sentiment '{sentiment.value}' is too long. "
                    f"Maximum: {self.MAX_CUSTOM_SENTIMENT_INSTRUCTIONS_LENGTH[1]} characters."
                )

    @property
    def system_prompt(self) -> str:
        return self.custom_system_prompt or self._default_system_prompt()

    @property
    def sentiment_instructions(self) -> Dict[Sentiment, str]:
        return self.custom_sentiment_instructions or self._default_sentiment_instructions()

    def get_sentiment_instruction(self, sentiment: Sentiment) -> str:
        return self.sentiment_instructions.get(
            sentiment,
            self.sentiment_instructions[Sentiment.neutral]
        )

    @staticmethod
    def _default_system_prompt() -> str:
        return (
            "You are an intelligent and helpful assistant. "
            "You have access to tools to answer questions about documents. "
            "Use the tools when necessary to provide accurate answers."
        )

    @staticmethod
    def _default_sentiment_instructions() -> Dict[Sentiment, str]:
        return {
            Sentiment.positive: (
                "The user is happy and has a positive attitude. "
                "Use a friendly, optimistic tone and appropriate emojis when natural. 😊"
            ),
            Sentiment.neutral: (
                "The user has a neutral and professional tone. "
                "Keep a polite, clear, and direct tone without being overly formal."
            ),
            Sentiment.negative: (
                "The user is frustrated, upset, or dissatisfied. "
                "Be empathetic, patient, and professional. Avoid emojis. "
                "Focus on resolving their issue effectively."
            )
        }
