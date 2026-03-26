import logging
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class FragmentSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FRAGMENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    vector_dimension: int = Field(gt=0)
