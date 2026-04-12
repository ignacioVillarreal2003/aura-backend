from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class QueryRewriteSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="QUERY_REWRITE_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    enabled: bool = Field(default=True)
    history_window: int = Field(default=4, ge=1, le=20)
