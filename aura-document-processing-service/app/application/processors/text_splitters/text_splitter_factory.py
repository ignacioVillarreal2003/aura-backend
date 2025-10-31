"""
Este módulo define una fábrica para instanciar diferentes divisores de texto (text splitters) 
según el método especificado. Facilita la selección y uso de distintos algoritmos de segmentación 
de texto de manera centralizada y extensible.

Uso principal:
    - Selección dinámica de la estrategia de división de texto en función de la configuración o el caso de uso.
    - Simplifica la integración de nuevos splitters en el sistema.
"""

from typing import Dict
from .interfaces.text_splitter_interface import TextSplitterInterface
from .token_based_text_splitter import TokenBasedTextSplitter
from .spacy_based_text_splitter import SpacyBasedTextSplitter
from .sentence_transformer_based_text_splitter import SentenceTransformerBasedTextSplitter
from .semantic_based_text_splitter import SemanticBasedTextSplitter
from .recursive_based_text_splitter import RecursiveBasedTextSplitter
from .huggingface_based_text_splitter import HuggingfaceBasedTextSplitter
from .char_tiktoken_based_text_splitter import CharTiktokenBasedTextSplitter
from .char_based_text_splitter import CharBasedTextSplitter


class TextSplitterFactory:
    """
    Fábrica para obtener instancias de divisores de texto según el método solicitado.

    Métodos:
        get_splitter(method: str) -> TextSplitterInterface:
            Devuelve una instancia del divisor de texto correspondiente al método especificado.

    Raises:
        ValueError: Si el método solicitado no está soportado.
    """
    def __init__(self):
        self._splitters: Dict[str, TextSplitterInterface] = {
            "token": TokenBasedTextSplitter(),
            "spacy": SpacyBasedTextSplitter(),
            "sentence_transformer": SentenceTransformerBasedTextSplitter(),
            "semantic": SemanticBasedTextSplitter(),
            "recursive": RecursiveBasedTextSplitter(),
            "huggingface": HuggingfaceBasedTextSplitter(),
            "char_tiktoken": CharTiktokenBasedTextSplitter(),
            "char": CharBasedTextSplitter()
        }

    def get_splitter(self, method: str) -> TextSplitterInterface:
        """
        Obtiene el divisor de texto correspondiente al método especificado.

        Args:
            method (str): Nombre del método de división de texto.

        Returns:
            TextSplitterInterface: Instancia del divisor de texto.

        Raises:
            ValueError: Si el método no está soportado.
        """
        if method not in self._splitters:
            raise ValueError(f"Método de chunking no soportado: {method}")
        return self._splitters[method]
