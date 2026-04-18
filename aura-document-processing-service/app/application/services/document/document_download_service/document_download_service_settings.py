from typing import ClassVar
from pydantic_settings import BaseSettings, SettingsConfigDict


class DocumentDownloadServiceSettings(BaseSettings):
    REQUIRED_PERMISSIONS: ClassVar[frozenset[str]] = frozenset({"DOCUMENT_GET"})

    model_config = SettingsConfigDict(
        env_prefix="DOCUMENT_DOWNLOAD_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
