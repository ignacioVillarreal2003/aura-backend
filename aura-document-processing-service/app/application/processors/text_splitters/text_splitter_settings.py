import logging
from typing import Literal, Optional
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

    active_type: TextSplitterType = Field(default=TextSplitterType.docling_hybrid)
    structured_fallback_type: TextSplitterType = Field(default=TextSplitterType.huggingface)

    max_text_length: int = Field(default=10_000_000, gt=0)
    min_chunk_chars: int = Field(default=150, ge=0)

    huggingface_model: str = Field(default="BAAI/bge-m3")
    huggingface_device: Literal["cpu", "cuda"] = Field(default="cuda")
    huggingface_normalize_embeddings: bool = Field(default=True)
    huggingface_max_seq_length: Optional[int] = Field(default=8192, gt=0, le=8192)
    huggingface_torch_dtype: Literal["auto", "float32", "float16", "bfloat16"] = Field(default="auto")
    huggingface_breakpoint_threshold_type: Literal[
        "percentile",
        "standard_deviation",
        "interquartile",
        "gradient"
    ] = Field(default="percentile")
    huggingface_breakpoint_threshold_amount: float | None = Field(default=None, gt=0)
    huggingface_max_chunk_tokens: int = Field(default=510, gt=0, le=512)
    huggingface_chunk_token_overlap: int = Field(default=50, ge=0, le=256)

    recursive_split_size: int = Field(default=512, gt=0, le=8192)
    recursive_split_overlap: int = Field(default=50, ge=0, le=8192)
    recursive_encoding_name: str = Field(default="cl100k_base")

    docling_tokenizer_model: str = Field(default="BAAI/bge-m3")
    docling_max_tokens: int = Field(default=512, gt=0, le=8192)
    docling_merge_peers: bool = Field(default=True)
    docling_device: Literal["cpu", "cuda", "mps", "auto"] = Field(default="auto")
    docling_num_threads: int = Field(default=4, ge=1, le=16)
    docling_artifacts_path: Optional[str] = Field(default=None)

    @model_validator(
        mode="after"
    )
    def validate_active_splitter_settings(
            self
    ) -> "TextSplitterSettings":
        self._validate_common()

        if self.structured_fallback_type == TextSplitterType.docling_hybrid:
            raise ValueError("structured_fallback_type must be a flat-text splitter, not docling_hybrid.")

        if self.active_type == TextSplitterType.docling_hybrid:
            self._validate_docling()

        effective_type = (
            self.structured_fallback_type
            if self.active_type == TextSplitterType.docling_hybrid
            else self.active_type
        )
        if effective_type == TextSplitterType.recursive:
            self._validate_recursive()
        elif effective_type == TextSplitterType.huggingface:
            self._validate_huggingface()
        return self

    def _validate_common(
            self
    ) -> None:
        smallest_chunk = min(self.recursive_split_size, self.huggingface_max_chunk_tokens)
        if self.max_text_length < smallest_chunk:
            raise ValueError("max_text_length must be greater than or equal to configured split sizes.")

    def _validate_docling(
            self
    ) -> None:
        if (not self.docling_tokenizer_model
                or not self.docling_tokenizer_model.strip()):
            raise ValueError("docling_tokenizer_model is required when active_type is docling_hybrid.")
        self.docling_tokenizer_model = self.docling_tokenizer_model.strip()

    def _validate_huggingface(
            self
    ) -> None:
        if (not self.huggingface_model
                or not self.huggingface_model.strip()):
            raise ValueError("huggingface_model is required when the Hugging Face splitter is active.")

        self.huggingface_model = self.huggingface_model.strip()
        if self.huggingface_breakpoint_threshold_amount is not None and self.huggingface_breakpoint_threshold_amount <= 0:
            raise ValueError("The Hugging Face breakpoint threshold amount must be greater than zero.")

        if self.huggingface_chunk_token_overlap >= self.huggingface_max_chunk_tokens:
            raise ValueError(
                "huggingface_chunk_token_overlap must be strictly smaller than huggingface_max_chunk_tokens.")

    def _validate_recursive(
            self
    ) -> None:
        if (not self.recursive_encoding_name
                or not self.recursive_encoding_name.strip()):
            raise ValueError("recursive_encoding_name is required when the recursive splitter is active.")
        self.recursive_encoding_name = self.recursive_encoding_name.strip()

        if self.recursive_split_overlap >= self.recursive_split_size:
            raise ValueError("Chunk overlap must be strictly smaller than chunk size for the recursive splitter.")
