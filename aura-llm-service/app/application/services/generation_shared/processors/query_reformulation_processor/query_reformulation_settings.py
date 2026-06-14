from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class QueryReformulationSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="QUERY_REFORMULATION_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    history_messages_window: int = Field(default=4, ge=0, le=20)
    use_keywords: bool = Field(default=True)
