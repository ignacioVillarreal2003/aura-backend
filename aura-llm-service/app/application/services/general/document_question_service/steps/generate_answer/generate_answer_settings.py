from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class GenerateAnswerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GENERATE_ANSWER_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    history_window: int = Field(default=5, ge=0, le=20)
