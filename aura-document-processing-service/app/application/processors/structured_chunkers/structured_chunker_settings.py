from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class StructuredChunkerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="STRUCTURED_CHUNKER_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Tokenizer used by the Docling HybridChunker to keep chunks within the
    # embedding model's context window. Align this with the embedder model so a
    # chunk that fits here also fits the embedder.
    tokenizer_model: str = Field(
        default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    max_tokens: int = Field(default=512, gt=0, le=8192)

    # Merge undersized adjacent chunks that share the same headings.
    merge_peers: bool = Field(default=True)

    device: Literal["cpu", "cuda", "mps", "auto"] = Field(default="auto")
    num_threads: int = Field(default=4, ge=1, le=16)

    # Upper bound on the source text length (chars) accepted before chunking.
    max_text_length: int = Field(default=10_000_000, gt=0)
