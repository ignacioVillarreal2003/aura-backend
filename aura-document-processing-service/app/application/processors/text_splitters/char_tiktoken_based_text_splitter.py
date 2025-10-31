"""División de texto por tokens usando tiktoken.

Este módulo ofrece un splitter que utiliza el codificador de `tiktoken`
compatibile con modelos GPT (OpenAI). La segmentación resultante respeta los
límites reales de tokens de dichos modelos.

Dependencies:
  - langchain-text-splitters
  - tiktoken

Notes:
  - Produce fragmentos alineados con la tokenización de modelos GPT.
  - Recomendado cuando embeddings/respuestas se generan con modelos OpenAI.
  - A diferencia del enfoque por caracteres, respeta límites de tokens.
"""

from langchain_text_splitters import CharacterTextSplitter
from typing import List
from .interfaces.text_splitter_interface import TextSplitterInterface


class CharTiktokenBasedTextSplitter(TextSplitterInterface):
    """Splitter basado en `tiktoken` para conteo real de tokens.

    Genera fragmentos controlados por número de tokens con la misma
    tokenización usada por modelos GPT compatibles con `tiktoken`.
    """
    def split_text(self, text: str, size: int = 50, overlap: int = 20) -> List[str]:
        """Divide texto en fragmentos según tokenización `tiktoken`.

        Args:
            text: Texto de entrada a fragmentar.
            size: Número máximo de tokens por fragmento.
            overlap: Tokens superpuestos entre fragmentos consecutivos.

        Returns:
            Lista de fragmentos de texto.
        """
        splitter = CharacterTextSplitter.from_tiktoken_encoder(
            encoding_name="cl100k_base",
            chunk_size=size,
            chunk_overlap=overlap,
            separator="\n"
        )
        return splitter.split_text(text)