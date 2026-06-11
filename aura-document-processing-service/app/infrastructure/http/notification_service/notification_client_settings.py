from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class NotificationClientSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="NOTIFICATION_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Same env var names used by the other producer services:
    # NOTIFICATION_SERVICE_URL and NOTIFICATION_INTERNAL_API_TOKEN.
    service_url: Optional[str] = Field(default=None)
    internal_api_token: Optional[str] = Field(default=None)
    request_timeout_seconds: float = Field(default=5.0, gt=0, le=60.0)
