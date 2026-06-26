from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TimelineSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TIMELINE_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    max_title_chars: int = Field(default=100, ge=1, le=1_000)
    max_description_chars: int = Field(default=1_000, ge=100, le=20_000)
    max_event_title_chars: int = Field(default=300, ge=1, le=5_000)
    max_event_description_chars: int = Field(default=2_000, ge=100, le=50_000)
    max_event_occurred_label_chars: int = Field(default=100, ge=1, le=1_000)
    max_events: int = Field(default=50, ge=1, le=200)
