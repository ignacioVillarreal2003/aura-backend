from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RedisCoordinationSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="REDIS_COORDINATION_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    url: str = Field(
        default="redis://127.0.0.1:6379/0",
        description="Redis URL shared by post-process job state and content deduplication.",
    )
    key_prefix: str = Field(default="aura:coordination", max_length=128)
    post_process_job_lock_ttl_seconds: int = Field(default=86_400, ge=300, le=2_592_000)
