from typing import Optional
from urllib.parse import urlparse
from pydantic import Field, field_validator, model_validator
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

    @field_validator("membership_url", mode="before")
    @classmethod
    def validate_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = str(v).strip().rstrip("/")
        if not v:
            return None
        if not v.startswith(("http://", "https://")):
            raise ValueError("The chat service URL must start with http:// or https://.")
        return v

    @model_validator(mode="after")
    def validate_url_host(self) -> "ChatMembershipProviderSettings":
        if self.membership_url is not None and not urlparse(self.membership_url).netloc:
            raise ValueError("The chat service URL must include a valid host.")
        return self
