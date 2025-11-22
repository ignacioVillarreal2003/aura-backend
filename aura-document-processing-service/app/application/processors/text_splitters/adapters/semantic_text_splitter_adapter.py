from langchain_experimental.text_splitter import SemanticChunker
from langchain_huggingface import HuggingFaceEmbeddings
from typing import Literal

from app.application.exceptions.api_exceptions import TextSplitterError
from app.application.processors.text_splitters.interfaces.text_splitter_interface import TextSplitterInterface


class SemanticTextSplitterAdapter(TextSplitterInterface):
    def split_text(self,
                   text: str,
                   size: int,
                   overlap: int) -> list[str]:
        try:
            breakpoint_type: Literal["percentile", "standard_deviation", "interquartile", "gradient"] = "percentile"
            model_name: str = "sentence-transformers/all-MiniLM-L6-v2"

            embeddings = HuggingFaceEmbeddings(model_name=model_name)
            splitter = SemanticChunker(
                embeddings,
                breakpoint_threshold_type=breakpoint_type
            )
            return splitter.split_text(text)
        except Exception as e:
            raise TextSplitterError(f"Error al generar splits de texto con SemanticTextSplitterAdapter: {str(e)}")
