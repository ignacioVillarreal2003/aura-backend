import logging
import re
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.application.processors.text_splitters.constants.text_splitter_type import TextSplitterType

logger = logging.getLogger(__name__)

_DEVICE_PATTERN = re.compile(r"^(cpu|cuda|mps)$")
_ALLOWED_ENCODINGS = frozenset({"cl100k_base", "gpt2"})
_ALLOWED_BREAKPOINT_TYPES = frozenset({"percentile", "standard_deviation", "interquartile", "gradient"})


class TextSplitterSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TEXT_SPLITTER_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    active_type: TextSplitterType = Field(default=TextSplitterType.recursive)
    max_text_length: int = Field(default=10_000_000, gt=0)

    recursive_split_size: int = Field(default=512, gt=0, le=8192)
    recursive_split_overlap: int = Field(default=50, ge=0, le=8192)
    recursive_encoding_name: str = Field(default="cl100k_base")

    huggingface_model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2")
    huggingface_device: str = Field(default="cpu")
    huggingface_breakpoint_threshold_type: str = Field(default="percentile")
    huggingface_breakpoint_threshold_amount: float | None = Field(default=None)

    markdown_processor_split_size: int = Field(default=512, gt=0, le=8192)
    markdown_processor_split_overlap: int = Field(default=50, ge=0, le=8192)
    markdown_processor_encoding_name: str = Field(default="cl100k_base")

    @model_validator(mode="after")
    def validate_active_splitter_settings(self) -> "TextSplitterSettings":
        if self.active_type == TextSplitterType.recursive:
            self._validate_recursive()
        elif self.active_type == TextSplitterType.huggingface:
            self._validate_huggingface()
        elif self.active_type == TextSplitterType.markdown_processor:
            self._validate_markdown_processor()
        return self

    def _validate_recursive(self) -> None:
        if self.recursive_split_overlap >= self.recursive_split_size:
            raise ValueError(
                f"recursive_split_overlap ({self.recursive_split_overlap}) "
                f"must be strictly less than recursive_split_size ({self.recursive_split_size})"
            )

        if self.recursive_encoding_name not in _ALLOWED_ENCODINGS:
            raise ValueError(
                f"recursive_encoding_name must be one of {_ALLOWED_ENCODINGS}, "
                f"got '{self.recursive_encoding_name}'"
            )

    def _validate_huggingface(self) -> None:
        if not self.huggingface_model or not self.huggingface_model.strip():
            raise ValueError("huggingface_model cannot be empty")

        self.huggingface_model = self.huggingface_model.strip()

        device = self.huggingface_device.lower()

        if not _DEVICE_PATTERN.match(device):
            raise ValueError(
                f"huggingface_device must be one of 'cpu', 'cuda', or 'mps', "
                f"got '{self.huggingface_device}'"
            )

        self.huggingface_device = device

        if self.huggingface_breakpoint_threshold_type not in _ALLOWED_BREAKPOINT_TYPES:
            raise ValueError(
                f"huggingface_breakpoint_threshold_type must be one of {_ALLOWED_BREAKPOINT_TYPES}, "
                f"got '{self.huggingface_breakpoint_threshold_type}'"
            )

        if (self.huggingface_breakpoint_threshold_amount is not None
                and self.huggingface_breakpoint_threshold_amount <= 0):
            raise ValueError(
                "huggingface_breakpoint_threshold_amount must be positive "
                f"if provided, got {self.huggingface_breakpoint_threshold_amount}"
            )

    def _validate_markdown_processor(self) -> None:
        if self.markdown_processor_split_overlap >= self.markdown_processor_split_size:
            raise ValueError(
                f"markdown_processor_split_overlap ({self.markdown_processor_split_overlap}) "
                f"must be strictly less than markdown_processor_split_size ({self.markdown_processor_split_size})"
            )
        if self.markdown_processor_encoding_name not in _ALLOWED_ENCODINGS:
            raise ValueError(
                f"markdown_processor_encoding_name must be one of {_ALLOWED_ENCODINGS}, "
                f"got '{self.markdown_processor_encoding_name}'"
            )
