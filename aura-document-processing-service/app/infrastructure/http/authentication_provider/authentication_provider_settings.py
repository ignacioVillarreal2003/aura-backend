from pydantic import Field, field_validator
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
