from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ValidateDocumentRequestSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="VALIDATE_SUMMARY_REQUEST_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    min_document_id: int = Field(default=1, ge=1)
    max_document_id: int = Field(default=2_147_483_647, ge=1)
