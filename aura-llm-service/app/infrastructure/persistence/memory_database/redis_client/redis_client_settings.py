from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class RedisClientSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="REDIS_CLIENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    url: SecretStr = Field(...)
    max_connections: int = Field(default=10, ge=1, le=200)
    socket_connect_timeout: float = Field(default=5.0, ge=0.5, le=30.0)
    socket_timeout: float = Field(default=10.0, ge=0.5, le=60.0)
    health_check_interval: int = Field(default=30, ge=0, le=300)
    retry_attempts: int = Field(default=3, ge=0, le=10)
