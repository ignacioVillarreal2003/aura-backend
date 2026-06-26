from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LessonsLearnedSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LESSONS_LEARNED_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    max_title_chars: int = Field(default=100, ge=1, le=1_000)
    max_narrative_chars: int = Field(default=4_000, ge=100, le=100_000)
    max_observation_chars: int = Field(default=2_000, ge=100, le=50_000)
    max_items: int = Field(default=100, ge=1, le=100)
