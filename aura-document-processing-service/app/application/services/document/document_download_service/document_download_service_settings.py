from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DocumentDownloadServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DOCUMENT_DOWNLOAD_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    download_chunk_size_bytes: int = Field(default=262_144, ge=16_384, le=4_194_304)
