from typing import Optional
from urllib.parse import urlparse
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthenticationProviderSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AUTHENTICATION_PROVIDER_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    authentication_url: str = Field(...)

    request_timeout_seconds: float = Field(default=15.0, gt=0, le=120.0)

    max_bearer_token_characters: int = Field(default=8192, ge=256, le=65536)

    token_cache_ttl_seconds: int = Field(default=60, ge=1, le=86400)

    allowed_authentication_hosts: Optional[str] = Field(default=None)

    @field_validator(
        "authentication_url",
        mode="before"
    )
    @classmethod
    def validate_url(
            cls,
            v: str
    ) -> str:
        v = v.strip().rstrip("/")
        if not v.startswith(("http://", "https://")):
            raise ValueError("The authentication service URL must start with http:// or https://.")
        return v

    @model_validator(mode="after")
    def validate_url_host_and_allowlist(
            self
    ) -> "AuthenticationProviderSettings":
        parsed = urlparse(self.authentication_url)
        if not parsed.netloc:
            raise ValueError("The authentication service URL must include a valid host.")

        if self.allowed_authentication_hosts:
            allowed = {
                h.strip().lower()
                for h in self.allowed_authentication_hosts.split(",")
                if h.strip()
            }
            if not allowed:
                return self
            host = (parsed.hostname or "").lower()
            if host not in allowed:
                raise ValueError(
                    "The authentication service host is not listed in AUTHENTICATION_PROVIDER_ALLOWED_AUTHENTICATION_HOSTS."
                )

        return self
