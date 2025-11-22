from langchain_text_splitters import SentenceTransformersTokenTextSplitter

from app.application.exceptions.api_exceptions import TextSplitterError
from app.application.processors.text_splitters.interfaces.text_splitter_interface import TextSplitterInterface


class SentenceTransformerTextSplitterAdapter(TextSplitterInterface):
    def split_text(self,
                   text: str,
                   size: int,
                   overlap: int) -> list[str]:
        try:
            model_name: str = "sentence-transformers/all-mpnet-base-v2"
            splitter = SentenceTransformersTokenTextSplitter(
                tokens_per_chunk=size,
                chunk_overlap=overlap,
                model_name=model_name,
            )
            return splitter.split_text(text)
        except Exception as e:
            raise TextSplitterError(f"Error al generar splits de texto con SentenceTransformerTextSplitterAdapter: {str(e)}")
