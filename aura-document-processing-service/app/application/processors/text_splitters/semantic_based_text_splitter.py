"""División basada en coherencia semántica con embeddings.

Este módulo incorpora un splitter que detecta caídas de similitud entre
oraciones (via embeddings) para determinar puntos de corte naturales, generando
fragmentos coherentes a nivel contextual.

Dependencies:
  - langchain-experimental
  - langchain-huggingface
  - sentence-transformers
  - torch

Notes:
  - Mide similitud coseno entre oraciones contiguas y corta en rupturas.
  - Ideal para RAG, búsqueda semántica y resúmenes contextuales.
  - Más costoso que enfoques por tokens o caracteres, pero produce cortes
    más significativos.
"""

from langchain_experimental.text_splitter import SemanticChunker
from langchain_huggingface import HuggingFaceEmbeddings
from typing import Literal, List

from app.application.processors.text_splitters.interfaces.text_splitter_interface import TextSplitterInterface


class SemanticBasedTextSplitter(TextSplitterInterface):
    """Splitter que corta por rupturas semánticas detectadas por embeddings.

    Utiliza un `SemanticChunker` con embeddings Hugging Face para encontrar
    breakpoints donde decae la coherencia entre oraciones.
    """
    def split_text(self, text: str, size: int = 100, overlap: int = 20) -> List[str]:
        """Divide texto detectando caídas de similitud semántica.

        Args:
            text: Texto de entrada a fragmentar.
            size: Tamaño de referencia para ajustar granularidad del análisis.
            overlap: Parámetro de compatibilidad; no se aplica directamente.

        Returns:
            Lista de fragmentos de texto.
        """
        breakpoint_type: Literal["percentile", "standard_deviation", "interquartile", "gradient"] = "percentile"
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2"

        embeddings = HuggingFaceEmbeddings(model_name=model_name)
        splitter = SemanticChunker(
            embeddings,
            breakpoint_threshold_type=breakpoint_type
        )
        return splitter.split_text(text)
