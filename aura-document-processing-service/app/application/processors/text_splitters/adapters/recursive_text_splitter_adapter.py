import logging

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.application.processors.text_splitters.exceptions.text_splitter_exception import TextSplitterException
from app.application.processors.text_splitters.interfaces.text_splitter_adapter_interface import (
    TextSplitterAdapterInterface
)

logger = logging.getLogger(__name__)


class RecursiveTextSplitterAdapter(TextSplitterAdapterInterface):
    def split_text(
            self,
            text: str,
            size: int,
            overlap: int
    ) -> list[str]:
        if not text or not text.strip():
            logger.warning("split_text received empty or blank text — returning empty list")
            return []

        try:
            # Uses cl100k_base tokenizer (same as nomic-embed-text context window)
            # Separators follow the default recursive order: \n\n, \n, space, ""
            splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
                encoding_name="cl100k_base",
                chunk_size=size,
                chunk_overlap=overlap,
            )
            chunks = splitter.split_text(text)
            logger.info(
                f"Text split completed [chunks={len(chunks)}, chunk_size={size}, overlap={overlap}]"
            )
            return chunks
        except Exception as e:
            raise TextSplitterException(
                f"Failed to split text with RecursiveTextSplitterAdapter: {e}"
            )
