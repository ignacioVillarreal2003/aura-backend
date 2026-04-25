import logging
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.application.processors.text_cleaners.constants.text_cleaner_type import TextCleanerType

logger = logging.getLogger(__name__)


class TextCleanerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TEXT_CLEANER_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    active_type: TextCleanerType = Field(default=TextCleanerType.simple)
    max_text_length: int = Field(default=10_000_000, gt=0)

    simple_remove_urls: bool = Field(default=True)
    simple_remove_emojis: bool = Field(default=True)
    simple_remove_markdown: bool = Field(default=True)
    simple_normalize_whitespace: bool = Field(default=True)
    simple_remove_noise_lines: bool = Field(default=True)
    simple_join_fragmented_lines: bool = Field(default=True)

    @model_validator(
        mode="after"
    )
    def validate_active_cleaner_settings(
            self
    ) -> "TextCleanerSettings":
        if self.active_type == TextCleanerType.simple:
            self._validate_simple()
        return self

    def _validate_simple(
            self
    ) -> None:
        options_enabled = (
            self.simple_remove_urls
            or self.simple_remove_emojis
            or self.simple_remove_markdown
            or self.simple_normalize_whitespace
            or self.simple_remove_noise_lines
            or self.simple_join_fragmented_lines
        )
        if not options_enabled:
            raise ValueError("At least one simple cleaner option must be enabled.")
