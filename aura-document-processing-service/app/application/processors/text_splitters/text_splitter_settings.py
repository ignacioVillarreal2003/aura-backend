import logging
from typing import Literal
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.application.processors.text_splitters.constants.text_splitter_type import TextSplitterType

logger = logging.getLogger(__name__)


class TextSplitterSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TEXT_SPLITTER_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    active_type: TextSplitterType = Field(default=TextSplitterType.recursive)

    max_text_length: int = Field(default=10_000_000, gt=0)

    huggingface_model: Literal[
                           "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                           "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
                           "intfloat/multilingual-e5-large",
                       ] | str = Field(default="sentence-transformers/all-MiniLM-L6-v2")
    huggingface_device: Literal["cpu", "cuda"] = Field(default="cpu")
    huggingface_breakpoint_threshold_type: Literal[
        "percentile",
        "standard_deviation",
        "interquartile",
        "gradient"
    ] = Field(default="percentile")
    huggingface_breakpoint_threshold_amount: float | None = Field(default=None, gt=0)

    recursive_split_size: int = Field(default=512, gt=0, le=8192)
    recursive_split_overlap: int = Field(default=50, ge=0, le=8192)
    recursive_encoding_name: Literal[
                                 "cl100k_base",
                                 "gpt2"
                             ] | str = Field(default="cl100k_base")

    markdown_processor_split_size: int = Field(default=512, gt=0, le=8192)
    markdown_processor_split_overlap: int = Field(default=50, ge=0, le=8192)
    markdown_processor_encoding_name: Literal[
                                          "cl100k_base",
                                          "gpt2"
                                      ] | str = Field(default="cl100k_base")

    @model_validator(
        mode="after"
    )
    def validate_active_splitter_settings(
            self
    ) -> "TextSplitterSettings":
        if self.active_type == TextSplitterType.recursive:
            self._validate_recursive()
        elif self.active_type == TextSplitterType.huggingface:
            self._validate_huggingface()
        elif self.active_type == TextSplitterType.markdown_processor:
            self._validate_markdown_processor()
        return self

    def _validate_huggingface(
            self
    ) -> None:
        if (not self.huggingface_model
                or not self.huggingface_model.strip()):
            raise ValueError("The Hugging Face model name cannot be empty.")

        self.huggingface_model = self.huggingface_model.strip()

    def _validate_recursive(
            self
    ) -> None:
        if self.recursive_split_overlap >= self.recursive_split_size:
            raise ValueError("Chunk overlap must be strictly smaller than chunk size for the recursive splitter.")

    def _validate_markdown_processor(
            self
    ) -> None:
        if self.markdown_processor_split_overlap >= self.markdown_processor_split_size:
            raise ValueError("Chunk overlap must be strictly smaller than chunk size for the markdown splitter.")
