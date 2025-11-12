"""Embeddings con modelos de Hugging Face.

Usa `HuggingFaceEmbeddings` para calcular embeddings de documentos y consultas
con modelos de la plataforma Hugging Face.

Dependencias:
  - langchain-huggingface

Modelos (ejemplos habituales):
  - sentence-transformers/all-MiniLM-L6-v2 (rápido, 384d, multilingüe)
  - sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 (mejor calidad)
  - sentence-transformers/distiluse-base-multilingual-cased-v2 (balanceado)
  - intfloat/multilingual-e5-base (robusto, 768d)
  - intfloat/multilingual-e5-large (mayor precisión, 1024d)
  - BAAI/bge-m3 (potente para búsqueda semántica)

Notas:
  - Mientras más grande el modelo, mayor costo de cómputo.
"""
from typing import List
from langchain_huggingface import HuggingFaceEmbeddings

from app.application.processors.embeddings.interfaces.embedding_interface import EmbeddingInterface


class HuggingfaceBasedEmbedding(EmbeddingInterface):
    """Proveedor de embeddings basado en Hugging Face.

    Permite elegir el modelo vía `model_name` y el dispositivo si se desea
    acelerar la inferencia (por ejemplo, GPU si está disponible).
    """
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2", device: str | None = None):
        self.model_name = model_name
        self.device = device
        self.embeddings_model = HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs={"device": device} if device else {}
        )

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Vectoriza una lista de documentos.

        Args:
            texts: Documentos a vectorizar.

        Returns:
            Lista de vectores (uno por documento).
        """
        return self.embeddings_model.embed_documents(texts)

    def embed_query(self, text: str) -> List[float]:
        """Vectoriza una consulta individual.

        Args:
            text: Texto de consulta.

        Returns:
            Vector de embeddings de la consulta.
        """
        return self.embeddings_model.embed_query(text)

