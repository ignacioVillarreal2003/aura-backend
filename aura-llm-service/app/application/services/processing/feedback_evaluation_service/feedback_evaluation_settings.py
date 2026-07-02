from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class FeedbackEvaluationServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FEEDBACK_EVALUATION_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    max_query_chars: int = Field(default=4_000, ge=100, le=50_000)
    max_response_chars: int = Field(default=8_000, ge=100, le=50_000)
    max_comment_chars: int = Field(default=2_000, ge=0, le=20_000)
    max_history_chars: int = Field(default=12_000, ge=0, le=100_000)
    max_fragments_chars: int = Field(default=20_000, ge=0, le=200_000)
    max_repair_attempts: int = Field(default=1, ge=0, le=3)
