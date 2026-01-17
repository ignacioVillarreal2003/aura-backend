import logging
from dataclasses import dataclass
from typing import Final, Tuple

from app.application.services.agent_service.constants.sentimient import Sentiment

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class AgentConfiguration:
    MAX_MESSAGE_LENGTH: Final[Tuple[int, int]] = (1_000, 10_000)
    MAX_MESSAGES_COUNT: Final[Tuple[int, int]] = (4, 10)
    MAX_TOOL_ITERATIONS: Final[Tuple[int, int]] = (5, 10)

    DEFAULT_MESSAGE_LENGTH: Final[Tuple[int, int]] = (1, 1_000)
    DEFAULT_MAX_MESSAGES_COUNT: Final[int] = 4
    DEFAULT_MAX_TOOL_ITERATIONS: Final[int] = 5
    DEFAULT_SENTIMENT: Final[Sentiment] = Sentiment.NEUTRAL

    message_length: Tuple[int, int] = DEFAULT_MESSAGE_LENGTH
    max_messages_count: int = DEFAULT_MAX_MESSAGES_COUNT
    max_tool_iterations: int = DEFAULT_MAX_TOOL_ITERATIONS
    sentiment: Sentiment = DEFAULT_SENTIMENT

    def __post_init__(self) -> None:
        try:
            self._validate_all()
            logger.info(
                "AgentConfiguration initialized successfully",
                extra={
                    "message_length": self.message_length,
                    "max_messages_count": self.max_messages_count,
                    "max_tool_iterations": self.max_tool_iterations,
                    "sentiment": self.sentiment
                }
            )
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
        self._validate_message_length()
        self._validate_max_messages_count()
        self._validate_max_tool_iterations()
        self._validate_sentiment()

    def _validate_message_length(self) -> None:
        if not (self.MAX_MESSAGE_LENGTH[0]
                <= self.message_length[1]
                <= self.MAX_MESSAGE_LENGTH[1]):
            raise ValueError(
                f"max_message_length debe estar entre {self.MAX_MESSAGE_LENGTH[0]} y {self.MAX_MESSAGE_LENGTH[1]}, "
                f"se recibió: {self.message_length[1]}"
            )

        if self.message_length[0] < 1:
            raise ValueError(f"min_message_length no puede ser negativo, se recibió: {self.message_length[0]}")

        if self.message_length[0] > self.message_length[1]:
            raise ValueError(
                f"min_message_length ({self.message_length[0]}) no puede ser mayor que max_message_length ({self.message_length[1]})"
            )

    def _validate_max_messages_count(self) -> None:
        if not (self.MAX_MESSAGES_COUNT[0]
                <= self.max_messages_count
                <= self.MAX_MESSAGES_COUNT[1]):
            raise ValueError(
                f"max_messages_count debe estar entre {self.MAX_MESSAGES_COUNT[0]} y {self.MAX_MESSAGES_COUNT[1]}, "
                f"se recibió: {self.max_messages_count}"
            )

    def _validate_max_tool_iterations(self) -> None:
        if not (self.MAX_TOOL_ITERATIONS[0]
                <= self.max_tool_iterations
                <= self.MAX_TOOL_ITERATIONS[1]):
            raise ValueError(
                f"max_tool_iterations debe estar entre {self.MAX_TOOL_ITERATIONS[0]} y {self.MAX_TOOL_ITERATIONS[1]}, "
                f"se recibió: {self.max_tool_iterations}"
            )

    def _validate_sentiment(self) -> None:
        if not isinstance(self.sentiment, Sentiment):
            raise ValueError(f"sentiment debe ser una instancia de Sentiment, se recibió: {type(self.sentiment)}")
