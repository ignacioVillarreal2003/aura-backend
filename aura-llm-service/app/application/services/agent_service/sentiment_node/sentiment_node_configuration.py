import logging
from dataclasses import dataclass
from typing import Final, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class SentimentNodeConfiguration:
    MAX_CUSTOM_SYSTEM_PROMPT_LENGTH: Final[Tuple[int, int]] = (1_000, 10_000)
    DEFAULT_CUSTOM_SYSTEM_PROMPT_LENGTH: Final[Tuple[int, int]] = (1, 1_000)

    custom_system_prompt_length: Final[Tuple[int, int]] = DEFAULT_CUSTOM_SYSTEM_PROMPT_LENGTH
    custom_system_prompt: Optional[str] = None

    def __post_init__(self) -> None:
        try:
            self._validate_all()
            logger.debug("SentimentNodeConfiguration initialized")
        except ValueError as e:
            logger.error(
                "SentimentNodeConfiguration validation failed",
                extra={"error": str(e)},
                exc_info=True,
            )
            raise

    def _validate_all(self) -> None:
        if self.custom_system_prompt is not None:
            self._validate_custom_system_prompt()

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
                f"Maximum allowed: {self.MAX_CUSTOM_SYSTEM_PROMPT_LENGTH[1]} characters."
            )

    @property
    def system_prompt(self) -> str:
        return self.custom_system_prompt or self._default_system_prompt()

    @staticmethod
    def _default_system_prompt() -> str:
        return (
            "You are an expert sentiment classifier. "
            "Your task is to analyze the user's message and classify its emotional sentiment. "
            "You MUST respond with ONLY one of these three words: POSITIVE, NEGATIVE, NEUTRAL. "
            "Do not include explanations, punctuation, or any extra text."
        )
