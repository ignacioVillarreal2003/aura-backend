"""
Define la interfaz base para todos los proveedores de embeddings.
Obliga a implementar métodos para vectorizar documentos y consultas, garantizando
una API consistente para todas las implementaciones.

Uso principal:
    - Servir como contrato para la implementación de nuevos proveedores de embeddings.
    - Facilitar la integración e intercambio entre diferentes backends de embeddings.
"""
from abc import ABC, abstractmethod
from typing import List

class EmbeddingInterface(ABC):
    """
    Interfaz abstracta para proveedores de embeddings.

    Métodos abstractos:
        embed_documents(texts: List[str]) -> List[List[float]]:
            Calcula embeddings para múltiples documentos.
        embed_query(text: str) -> List[float]:
            Calcula embeddings para una consulta individual.

    Args:
        texts (List[str]): Documentos a vectorizar.
        text (str): Consulta a vectorizar.

    Returns:
        List[List[float]] | List[float]: Vectores de embeddings.
    """
    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        pass

    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        pass
