"""Embeddings con Sentence Transformers.

Utiliza la librería `sentence-transformers` para producir embeddings de alta
calidad en múltiples idiomas.

Dependencias:
  - sentence-transformers

Modelos (ejemplos):
  - paraphrase-multilingual-MiniLM-L12-v2 (multilingüe, ligero)
  - distiluse-base-multilingual-cased-v2 (mayor calidad)

Notas:
  - Los modelos se descargan automáticamente al primer uso.
"""
from typing import List
from sentence_transformers import SentenceTransformer
from app.application.processors.embeddings.interfaces.embedding_interface import EmbeddingInterface

class SentenceTransformerBasedEmbedding(EmbeddingInterface):
    """Proveedor de embeddings basado en Sentence Transformers.

    Carga un modelo por nombre y expone métodos para vectorizar documentos y
    consultas.
    """
    def __init__(self, model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"):
        self.model_name = model
        self.model = SentenceTransformer(model_name_or_path=self.model_name)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Vectoriza múltiples documentos.

        Args:
            texts: Documentos a vectorizar.

        Returns:
            Lista de vectores.
        """
        return self.model.encode(texts, convert_to_numpy=True).tolist()

    def embed_query(self, text: str) -> List[float]:
        """Vectoriza una consulta.

        Args:
            text: Texto de consulta.

        Returns:
            Vector de embeddings.
        """
        return self.model.encode(text, convert_to_numpy=True).tolist()

