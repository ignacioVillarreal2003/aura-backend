import logging
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.application.processors.embedders.constants.embedder_type import EmbedderType
from app.application.processors.text_cleaners.constants.text_cleaner_type import TextCleanerType
from app.application.processors.text_splitters.constants.text_splitter_type import TextSplitterType

logger = logging.getLogger(__name__)


class DocumentIngestionServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DOCUMENT_INGESTION_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    text_cleaner_type: TextCleanerType = Field(
        default=TextCleanerType.simple
    )
    text_splitter_type: TextSplitterType = Field(
        default=TextSplitterType.recursive
    )
    embedder_type: EmbedderType = Field(
        default=EmbedderType.ollama
    )

    batch_size: int = Field(
        default=100,
        gt=0,
        le=1000
    )
