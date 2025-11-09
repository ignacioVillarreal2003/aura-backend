"""División por tokens con tokenizadores de Hugging Face.

Este módulo ofrece un splitter que usa un tokenizador de Hugging Face (p. ej.,
`GPT2TokenizerFast`) para producir fragmentos alineados con la tokenización del
modelo seleccionado.

Dependencies:
  - langchain-text-splitters
  - transformers

Notes:
  - Compatible con cualquier tokenizador Hugging Face, no solo GPT-2.
  - Útil cuando se trabaja con modelos/embeddings de Hugging Face.
"""

from langchain_text_splitters import CharacterTextSplitter
from transformers import GPT2TokenizerFast
from typing import List

from app.application.processors.text_splitters.interfaces.text_splitter_interface import TextSplitterInterface


class HuggingfaceBasedTextSplitter(TextSplitterInterface):
    """Splitter que usa tokenizadores Hugging Face para contar tokens.

    Alinea la segmentación del texto con la tokenización real de un modelo
    Hugging Face, proporcionando control sobre tamaño y solapamiento.
    """
    def split_text(self, text: str, size: int = 50, overlap: int = 20) -> List[str]:
        """Divide texto usando un tokenizador de Hugging Face.

        Args:
            text: Texto de entrada a fragmentar.
            size: Máximo de tokens por fragmento.
            overlap: Tokens compartidos entre fragmentos consecutivos.

        Returns:
            Lista de fragmentos de texto.
        """
        tokenizer = GPT2TokenizerFast.from_pretrained("gpt2")
        splitter = CharacterTextSplitter.from_huggingface_tokenizer(
            tokenizer,
            chunk_size=size,
            chunk_overlap=overlap,
            separator="\n"
        )
        return splitter.split_text(text)
