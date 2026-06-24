from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SectionContextSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SECTION_CONTEXT_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Above this total size of secondary (section) context, condense it with the
    # LLM instead of sending it verbatim. Conservative so context never explodes.
    summarize_threshold_chars: int = Field(default=6_000, ge=500, le=200_000)

    # Hard cap for the condensed secondary block after summarization.
    max_section_context_chars: int = Field(default=4_000, ge=500, le=200_000)

    max_concurrent_groups: int = Field(default=4, ge=1, le=32)

    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
