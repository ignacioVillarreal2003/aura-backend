from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServiceAuthSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    internal_service_api_key: str = Field(...)
