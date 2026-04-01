from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ValidateRequestSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="VALIDATE_REQUEST_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    min_question_length: int = Field(default=1, ge=1)
    max_question_length: int = Field(default=1000, ge=1, le=10_000)
    max_history_messages: int = Field(default=10, ge=0, le=100)

    @model_validator(mode="after")
    def validate_question_length_range(self) -> "ValidateRequestSettings":
        if self.min_question_length > self.max_question_length:
            raise ValueError(
                f"min_question_length ({self.min_question_length}) must be "
                f"less than or equal to max_question_length ({self.max_question_length})"
            )
        return self
