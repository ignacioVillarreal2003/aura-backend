"""
Este módulo define una fábrica para instanciar diferentes proveedores de embeddings
según el método especificado. Facilita la selección y uso de distintas
implementaciones de embeddings de manera centralizada y extensible.

Uso principal:
    - Selección dinámica de la estrategia de embeddings en función de la configuración o el caso de uso.
    - Simplifica la integración de nuevos proveedores de embeddings en el sistema.
"""
from app.application.processors.embeddings.huggingface_based_embedding import HuggingfaceBasedEmbedding
from app.application.processors.embeddings.interfaces.embedding_interface import EmbeddingInterface
from typing import Dict

from app.application.processors.embeddings.ollama_based_embedding import OllamaBasedEmbedding
from app.application.processors.embeddings.sentence_transformer_based_embedding import SentenceTransformerBasedEmbedding
from app.application.processors.embeddings.spacy_based_embedding import SpacyBasedEmbedding


class EmbeddingsFactory:
    """
    Fábrica para obtener instancias de proveedores de embeddings según el método solicitado.

    Métodos:
        get_embedding(method: str) -> EmbeddingInterface:
            Devuelve una instancia del proveedor de embeddings correspondiente al método especificado.

    Raises:
        ValueError: Si el método solicitado no está soportado.
    """
    def __init__(self):
        self._embeddings: Dict[str, EmbeddingInterface] = {
            "huggingface": HuggingfaceBasedEmbedding(),
            "ollama": OllamaBasedEmbedding(),
            "sentence_transformer": SentenceTransformerBasedEmbedding(),
            "spacy": SpacyBasedEmbedding()
        }

    def get_embedding(self, method: str) -> EmbeddingInterface:
        """
        Obtiene el proveedor de embeddings correspondiente al método especificado.

        Args:
            method (str): Nombre del método de embeddings.

        Returns:
            EmbeddingInterface: Instancia del proveedor de embeddings.

        Raises:
            ValueError: Si el método no está soportado.
        """
        if method not in self._embeddings:
            raise ValueError(f"Método de embeddings no soportado: {method}")
        return self._embeddings[method]
