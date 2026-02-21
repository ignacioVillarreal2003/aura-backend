from langchain_text_splitters import SentenceTransformersTokenTextSplitter

from app.application.processors.text_splitters.exceptions.text_splitter_exception import TextSplitterException
from app.application.processors.text_splitters.interfaces.text_splitter_adapter_interface import (
    TextSplitterAdapterInterface
)


class SentenceTransformerTextSplitterAdapter(TextSplitterAdapterInterface):
    def split_text(
            self,
            text: str,
            size: int,
            overlap: int
    ) -> list[str]:
        try:
            model_name: str = "sentence-transformers/all-mpnet-base-v2"
            splitter = SentenceTransformersTokenTextSplitter(
                tokens_per_chunk=size,
                chunk_overlap=overlap,
                model_name=model_name,
            )
            return splitter.split_text(text)
        except Exception as e:
            raise TextSplitterException(
                f"Error al generar splits de texto con SentenceTransformerTextSplitterAdapter: {str(e)}")
