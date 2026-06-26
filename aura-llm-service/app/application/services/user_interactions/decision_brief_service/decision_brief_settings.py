from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DecisionBriefSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DECISION_BRIEF_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    max_title_chars: int = Field(default=100, ge=1, le=1_000)
    max_narrative_chars: int = Field(default=4_000, ge=100, le=100_000)
    max_option_title_chars: int = Field(default=300, ge=1, le=2_000)
    max_option_text_chars: int = Field(default=2_000, ge=100, le=50_000)
    max_options: int = Field(default=10, ge=1, le=10)
