import logging
from dataclasses import dataclass
from typing import Final

from app.domain.constants.sentimient import Sentiment

logger = logging.getLogger(__name__)


@dataclass(
    frozen=True,
    kw_only=True
)
class AgentConfiguration:
    MIN_MESSAGE_LENGTH: Final[int] = 100
    MAX_MESSAGE_LENGTH: Final[int] = 10000

    MIN_HISTORY_MESSAGES_COUNT: Final[int] = 0
    MAX_HISTORY_MESSAGES_COUNT: Final[int] = 6

    MIN_TOOL_ITERATIONS: Final[int] = 1
    MAX_TOOL_ITERATIONS: Final[int] = 6

    DEFAULT_MIN_MESSAGE_LENGTH: Final[int] = 1
    DEFAULT_MAX_MESSAGE_LENGTH: Final[int] = 1000
    DEFAULT_MAX_HISTORY_MESSAGES_COUNT: Final[int] = 3
    DEFAULT_MAX_TOOL_ITERATIONS: Final[int] = 5
    DEFAULT_SENTIMENT: Final[Sentiment] = Sentiment.neutral
    DEFAULT_ENABLE_SENTIMENT: Final[bool] = True

    min_message_length: int = DEFAULT_MIN_MESSAGE_LENGTH
    max_message_length: int = DEFAULT_MAX_MESSAGE_LENGTH
    max_history_messages_count: int = DEFAULT_MAX_HISTORY_MESSAGES_COUNT
    max_tool_iterations: int = DEFAULT_MAX_TOOL_ITERATIONS
    sentiment: Sentiment = DEFAULT_SENTIMENT
    enable_sentiment_analysis: bool = DEFAULT_ENABLE_SENTIMENT

    def __post_init__(self) -> None:
        try:
            self._validate_all()
            logger.info(
                "AgentConfiguration initialized successfully",
                extra={
                    "min_question_length": self.min_message_length,
                    "max_question_length": self.max_message_length,
                    "max_history_messages_count": self.max_history_messages_count,
                    "max_tool_iterations": self.max_tool_iterations,
                    "sentiment": self.sentiment.value,
                    "enable_sentiment_analysis": self.enable_sentiment_analysis
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
        self._validate_max_message_length()
        self._validate_max_history_messages_count()
        self._validate_max_tool_iterations()
        self._validate_sentiment()

    def _validate_max_message_length(self) -> None:
        if not (self.MIN_MESSAGE_LENGTH
                <= self.max_message_length
                <= self.MAX_MESSAGE_LENGTH):
            raise ValueError(
                f"max_message_length debe estar entre {self.MIN_MESSAGE_LENGTH} y {self.MAX_MESSAGE_LENGTH}, "
                f"se recibió: {self.max_message_length}"
            )

        if self.min_message_length < 0:
            raise ValueError(
                f"min_message_length no puede ser negativo, se recibió: {self.min_message_length}"
            )

        if self.min_message_length > self.max_message_length:
            raise ValueError(
                f"min_message_length ({self.min_message_length}) no puede ser mayor que "
                f"max_message_length ({self.max_message_length})"
            )

    def _validate_max_history_messages_count(self) -> None:
        if not (self.MIN_HISTORY_MESSAGES_COUNT
                <= self.max_history_messages_count
                <= self.MAX_HISTORY_MESSAGES_COUNT):
            raise ValueError(
                f"max_history_messages_count debe estar entre {self.MIN_HISTORY_MESSAGES_COUNT} y {self.MAX_HISTORY_MESSAGES_COUNT}, "
                f"se recibió: {self.max_history_messages_count}"
            )

    def _validate_max_tool_iterations(self) -> None:
        if not (self.MIN_TOOL_ITERATIONS <= self.max_tool_iterations <= self.MAX_TOOL_ITERATIONS):
            raise ValueError(
                f"max_tool_iterations debe estar entre {self.MIN_TOOL_ITERATIONS} y {self.MAX_TOOL_ITERATIONS}, "
                f"se recibió: {self.max_tool_iterations}"
            )

    def _validate_sentiment(self) -> None:
        if not isinstance(self.sentiment, Sentiment):
            raise ValueError(
                f"default_sentiment debe ser una instancia de Sentiment, "
                f"se recibió: {type(self.sentiment)}"
            )
