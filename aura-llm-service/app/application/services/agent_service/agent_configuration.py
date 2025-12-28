from dataclasses import dataclass

from app.application.exceptions.app_exceptions import ValidationError
from app.domain.constants.sentimient import Sentiment


@dataclass(frozen=True)
class AgentConfiguration:
    max_tool_iterations: int = 5
    default_sentiment: Sentiment = Sentiment.neutral
    enable_sentiment_analysis: bool = True

    MIN_TOOL_ITERATIONS: int = 1
    MAX_TOOL_ITERATIONS: int = 20

    def __post_init__(self):
        if not (self.MIN_TOOL_ITERATIONS <=
                self.max_tool_iterations <=
                self.MAX_TOOL_ITERATIONS):
            raise ValidationError(
                f"max_tool_iterations must be between {self.MIN_TOOL_ITERATIONS} "
                f"and {self.MAX_TOOL_ITERATIONS}",
                status_code=500
            )