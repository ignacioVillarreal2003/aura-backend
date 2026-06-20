from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ChatMembershipProviderSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CHAT_SERVICE_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    membership_url: Optional[str] = Field(default=None)
    request_timeout_seconds: float = Field(default=15.0, gt=0, le=120.0)
