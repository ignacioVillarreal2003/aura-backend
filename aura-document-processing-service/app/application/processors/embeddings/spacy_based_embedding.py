"""Embeddings con vectores de spaCy.

Usa modelos de spaCy para obtener vectores de documentos y consultas. Adecuado
para prototipos y aplicaciones en español (u otros idiomas con modelos
disponibles).

Dependencias:
  - spacy

Modelos (ejemplos):
  - es_core_news_sm (rápido, prototipos)
  - es_core_news_md (mejor calidad)
  - es_core_news_lg (producción, embeddings más precisos)

Notas:
  - Algunos modelos requieren descargar vectores: `python -m spacy download ...`.
"""
from typing import List
import spacy
from app.application.processors.embeddings.interfaces.embedding_interface import EmbeddingInterface

class SpacyBasedEmbedding(EmbeddingInterface):
    """Proveedor de embeddings basado en spaCy.

    Carga un pipeline de spaCy y utiliza sus vectores para documentos y
    consultas.
    """
    def __init__(self, model_name: str = "es_core_news_sm"):
        self.model_name = model_name
        self.nlp = spacy.load(self.model_name)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Vectoriza múltiples documentos con vectores de spaCy.

        Args:
            texts: Documentos a vectorizar.

        Returns:
            Lista de vectores.
        """
        return [self.nlp(text).vector.tolist() for text in texts]

    def embed_query(self, text: str) -> List[float]:
        """Vectoriza una consulta con el pipeline de spaCy.

        Args:
            text: Texto de consulta.

        Returns:
            Vector de embeddings.
        """
        return self.nlp(text).vector.tolist()

