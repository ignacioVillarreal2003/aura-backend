from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MapActionChunksSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MAP_ACTION_CHUNKS_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    chunk_size: int = Field(default=5, ge=1, le=20)
    max_concurrent_chunks: int = Field(default=3, ge=1, le=10)
    max_retry_attempts: int = Field(default=3, ge=0, le=10)
    retry_delay: float = Field(default=1.0, ge=0.0, le=60.0)
