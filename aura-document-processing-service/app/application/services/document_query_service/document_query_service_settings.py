import logging
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.application.processors.embedders.constants.embedder_type import EmbedderType

logger = logging.getLogger(__name__)


class DocumentQueryServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DOCUMENT_QUERY_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    embedder_type: EmbedderType = Field(
        default=EmbedderType.ollama
    )

    max_fragments: int = Field(
        default=5,
        gt=0,
        le=100
    )

    max_question_length: int = Field(
        default=10000,
        gt=0,
        le=100000
    )

    min_question_length: int = Field(
        default=1,
        gt=0
    )

    @model_validator(mode="after")
    def validate_configuration_coherence(self) -> "DocumentQueryServiceSettings":
        if self.min_question_length >= self.max_question_length:
            raise ValueError(
                f"min_question_length ({self.min_question_length}) "
                f"must be strictly less than max_question_length ({self.max_question_length})"
            )
        return self
