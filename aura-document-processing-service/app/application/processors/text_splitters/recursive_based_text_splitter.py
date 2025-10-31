"""División recursiva con puntos de corte naturales.

Este módulo implementa un splitter que intenta segmentar primero por
separadores más amplios (párrafos, oraciones), y desciende recursivamente a
unidades más pequeñas (palabras, caracteres) hasta alcanzar el tamaño objetivo.

Dependencies:
  - langchain-text-splitters
  - tiktoken

Notes:
  - Mantiene estructura y coherencia mejor que el conteo fijo de caracteres.
  - Adecuado para textos de longitudes irregulares en pipelines RAG.
  - No depende de embeddings para lograr cortes naturales.
"""

from langchain_text_splitters import RecursiveCharacterTextSplitter
from typing import List
from .interfaces.text_splitter_interface import TextSplitterInterface


class RecursiveBasedTextSplitter(TextSplitterInterface):
    """Splitter recursivo con compatibilidad de tokenización.

    Intenta cortar por niveles (párrafos → oraciones → palabras) respetando
    un máximo de tokens y una superposición configurable.
    """
    def split_text(self, text: str, size: int = 200, overlap: int = 20) -> List[str]:
        """Divide texto recurriendo a niveles de granularidad decreciente.

        Args:
            text: Texto de entrada a fragmentar.
            size: Máximo de tokens por fragmento.
            overlap: Tokens compartidos entre fragmentos consecutivos.

        Returns:
            Lista de fragmentos de texto.
        """
        splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            model_name="gpt-4",
            chunk_size=size,
            chunk_overlap=overlap
        )
        return splitter.split_text(text)
