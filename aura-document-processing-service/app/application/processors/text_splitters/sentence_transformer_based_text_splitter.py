"""División por tokens usando tokenización de Sentence Transformers.

Este módulo ofrece un splitter que segmenta el texto alineado a la
tokenización exacta del modelo de embeddings seleccionado, garantizando
consistencia entre segmentación y vectorización.

Dependencies:
  - langchain-text-splitters
  - sentence-transformers
  - torch

Notes:
  - Evita desalineaciones entre cortes y límites reales de tokenización.
  - Adecuado cuando se usan embeddings de Sentence Transformers.
"""

from langchain_text_splitters import SentenceTransformersTokenTextSplitter
from typing import List

from app.application.processors.text_splitters.interfaces.text_splitter_interface import TextSplitterInterface


class SentenceTransformerBasedTextSplitter(TextSplitterInterface):
    """Splitter que usa la tokenización del modelo de Sentence Transformers.

    Genera fragmentos medidos en tokens del modelo para alinear segmentación y
    posterior vectorización con embeddings.
    """
    def split_text(self, text: str, size: int = 200, overlap: int = 20) -> List[str]:
        """Divide texto usando la tokenización del modelo de embeddings.

        Args:
            text: Texto de entrada a fragmentar.
            size: Tokens por fragmento según tokenizador del modelo.
            overlap: Tokens compartidos entre fragmentos consecutivos.

        Returns:
            Lista de fragmentos de texto.
        """
        model_name: str = "sentence-transformers/all-mpnet-base-v2"
        splitter = SentenceTransformersTokenTextSplitter(
            tokens_per_chunk=size,
            chunk_overlap=overlap,
            model_name=model_name,
        )
        return splitter.split_text(text)
