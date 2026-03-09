import logging
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class TextSplitterSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TEXT_SPLITTER_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    split_size: int = Field(
        default=512,
        gt=0,
        le=8192
    )
    split_overlap: int = Field(
        default=50,
        ge=0,
        le=8192
    )

    max_text_length: int = Field(
        default=10_000_000,
        gt=0
    )

    recursive_encoding_name: str = Field(
        default="cl100k_base"
    )

    @model_validator(
        mode="after"
    )
    def validate_split_coherence(
            self
    ) -> "TextSplitterSettings":
        if self.split_overlap >= self.split_size:
            raise ValueError(
                f"split_overlap ({self.split_overlap}) "
                f"must be strictly less than split_size ({self.split_size})"
            )

        return self

    @model_validator(
        mode="after"
    )
    def validate_recursive_encoding_name(
            self
    ) -> "TextSplitterSettings":
        allowed_encodings = ["cl100k_base", "gpt2"]
        if self.recursive_encoding_name not in allowed_encodings:
            raise ValueError(
                f"recursive_encoding_name must be one of {allowed_encodings}, "
                f"got '{self.recursive_encoding_name}'"
            )

        return self
