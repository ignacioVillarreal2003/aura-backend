import logging
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class FragmentQueryServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FRAGMENT_QUERY_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    max_fragments: int = Field(default=20, ge=1, le=100)
    min_question_length: int = Field(default=1, ge=1)
    max_question_length: int = Field(default=10_000, ge=1, le=100_000)

    @model_validator(mode="after")
    def validate_coherence(self) -> "FragmentQueryServiceSettings":
        if self.min_question_length >= self.max_question_length:
            raise ValueError(
                f"min_question_length ({self.min_question_length}) "
                f"must be strictly less than max_question_length ({self.max_question_length})"
            )
        return self
