from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ChecklistSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CHECKLIST_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    max_title_chars: int = Field(default=100, ge=1, le=1_000)
    max_description_chars: int = Field(default=1_000, ge=100, le=20_000)
    max_item_text_chars: int = Field(default=500, ge=1, le=10_000)
    max_section_chars: int = Field(default=200, ge=1, le=2_000)
    max_items: int = Field(default=20, ge=1, le=200)
