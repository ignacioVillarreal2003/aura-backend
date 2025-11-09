"""División de texto por conteo de caracteres.

Este módulo proporciona un splitter que trocea texto únicamente contando
caracteres, sin tokenización ni segmentación lingüística. Es simple, rápido y
predecible para crear fragmentos de tamaño uniforme.

Dependencias:
  - langchain-text-splitters

Notas:
  - No considera límites de palabras ni semántica; solo caracteres.
  - Útil para pruebas rápidas, textos cortos y pipelines RAG iniciales.
  - No requiere modelos ni tokenizadores externos.
"""

from langchain_text_splitters import CharacterTextSplitter
from typing import List

from app.application.processors.text_splitters.interfaces.text_splitter_interface import TextSplitterInterface


class CharBasedTextSplitter(TextSplitterInterface):
    """Splitter basado en conteo de caracteres.

    Crea fragmentos de texto de tamaño fijo en caracteres, con una
    superposición configurable entre fragmentos contiguos.
    """
    def split_text(self, text: str, size: int = 50, overlap: int = 20) -> List[str]:
        """Divide un texto en fragmentos por conteo de caracteres.

        Args:
            text: Texto de entrada a fragmentar.
            size: Número máximo de caracteres por fragmento.
            overlap: Cantidad de caracteres compartidos entre fragmentos consecutivos.

        Returns:
            Lista de fragmentos de texto.
        """
        splitter = CharacterTextSplitter(
            chunk_size=size,
            chunk_overlap=overlap,
            separator="\n"
        )
        return splitter.split_text(text)