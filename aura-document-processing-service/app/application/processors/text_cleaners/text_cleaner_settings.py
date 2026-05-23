import logging
from pydantic import Field
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
