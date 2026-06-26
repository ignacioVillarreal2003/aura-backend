from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class FragmentContextualizeServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FRAGMENT_CONTEXTUALIZE_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    max_content_chars: int = Field(default=20_000, ge=1_000, le=500_000)
    max_document_summary_chars: int = Field(default=2_000, ge=100, le=50_000)
