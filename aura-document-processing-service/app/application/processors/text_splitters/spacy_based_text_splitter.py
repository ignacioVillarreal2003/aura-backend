"""División respetando límites lingüísticos con spaCy.

Este módulo implementa un splitter que segmenta por unidades lingüísticas
naturales (por ejemplo, oraciones), lo que resulta especialmente útil para
textos extensos en español u otros idiomas soportados.

Dependencies:
  - langchain-text-splitters
  - spacy
  - Modelo spaCy (p. ej., `es_core_news_sm`)

Notes:
  - Favorece mantener oraciones completas para mejorar coherencia.
  - Requiere descargar el modelo spaCy del idioma correspondiente.
"""

from langchain_text_splitters import SpacyTextSplitter
from typing import List
from .interfaces.text_splitter_interface import TextSplitterInterface


class SpacyBasedTextSplitter(TextSplitterInterface):
    """Splitter que respeta límites de oraciones usando spaCy.

    Genera fragmentos controlados en tamaño procurando respetar límites
    lingüísticos definidos por el pipeline de spaCy.
    """
    def split_text(self, text: str, size: int = 200, overlap: int = 20) -> List[str]:
        pipeline: str = "es_core_news_sm"
        """Divide texto respetando límites de oración con spaCy.

        Args:
            text: Texto de entrada a fragmentar.
            size: Máximo de tokens por fragmento.
            overlap: Tokens compartidos entre fragmentos consecutivos.

        Returns:
            Lista de fragmentos de texto.
        """
        splitter = SpacyTextSplitter(
            chunk_size=size,
            chunk_overlap=overlap,
            pipeline=pipeline
        )
        return splitter.split_text(text)
