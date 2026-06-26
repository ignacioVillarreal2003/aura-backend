from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class QuizSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="QUIZ_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    max_title_chars: int = Field(default=100, ge=1, le=1_000)
    max_instructions_chars: int = Field(default=2_000, ge=100, le=50_000)
    max_question_chars: int = Field(default=1_000, ge=100, le=20_000)
    max_explanation_chars: int = Field(default=2_000, ge=100, le=50_000)
    max_option_chars: int = Field(default=500, ge=1, le=5_000)
    max_questions: int = Field(default=100, ge=1, le=100)
    max_options: int = Field(default=10, ge=2, le=10)
