from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PostProcessDocumentServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="POST_PROCESS_DOCUMENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    classify_sample_size: int = Field(default=40, ge=2, le=500)
