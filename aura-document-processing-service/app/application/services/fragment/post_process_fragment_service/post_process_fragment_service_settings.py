from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PostProcessFragmentServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="POST_PROCESS_FRAGMENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    fragment_page_size: int = Field(default=50, ge=1, le=500)
    max_document_ids: int = Field(default=500, ge=1, le=10000)
