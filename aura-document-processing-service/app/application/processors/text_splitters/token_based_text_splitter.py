"""División por conteo de tokens.

Este módulo incluye un splitter que crea fragmentos medidos en número de
tokens, permitiendo controlar tamaño y superposición con respecto a límites de
tokenización.

Dependencies:
  - langchain-text-splitters

Notes:
  - Asegura que los fragmentos respeten límites de tokens usados por modelos.
  - Adecuado para pipelines que consumen modelos basados en tokens.
"""

from langchain_text_splitters import TokenTextSplitter
from typing import List

from app.application.processors.text_splitters.interfaces.text_splitter_interface import TextSplitterInterface


class TokenBasedTextSplitter(TextSplitterInterface):
    """Splitter que trocea texto por número de tokens.

    Produce fragmentos limitados por tokens y con solapamiento configurable,
    independientes del significado lingüístico.
    """
    def split_text(self, text: str, size: int = 200, overlap: int = 20) -> List[str]:
        """Divide texto en fragmentos medidos en tokens.

        Args:
            text: Texto de entrada a fragmentar.
            size: Cantidad de tokens por fragmento.
            overlap: Tokens compartidos entre fragmentos consecutivos.

        Returns:
            Lista de fragmentos de texto.
        """
        splitter = TokenTextSplitter(
            chunk_size=size,
            chunk_overlap=overlap
        )
        return splitter.split_text(text)
