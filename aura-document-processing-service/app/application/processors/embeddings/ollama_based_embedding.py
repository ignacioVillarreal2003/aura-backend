"""Embeddings locales con Ollama.

Usa `OllamaEmbeddings` para generar embeddings a partir de modelos servidos por
Ollama localmente.

Dependencias:
  - langchain-ollama
  - Servicio Ollama en ejecución con el modelo disponible

Modelos (ejemplos):
  - nomic-embed-text:v1.5 (multilingüe, rápido y liviano)
  - Cualquier otro modelo instalado en Ollama (ver `ollama list`)

Notas:
  - Asegura que Ollama esté corriendo y el modelo descargado.
  - `keep_alive=True` mejora rendimiento con llamadas consecutivas.
"""
from typing import List
from langchain_ollama import OllamaEmbeddings
from app.application.processors.embeddings.interfaces.embedding_interface import EmbeddingInterface

class OllamaBasedEmbedding(EmbeddingInterface):
    """Proveedor de embeddings usando modelos servidos por Ollama.

    Permite configurar el nombre del modelo y el comportamiento de `keep_alive`.
    """
    def __init__(self, model: str = "nomic-embed-text:v1.5", keep_alive: bool = True):
        self.model_name = model
        self.keep_alive = keep_alive
        self.model = OllamaEmbeddings(model=self.model_name)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Vectoriza múltiples documentos usando el backend de Ollama.

        Args:
            texts: Documentos a vectorizar.

        Returns:
            Lista de vectores.
        """
        return self.model.embed_documents(texts)

    def embed_query(self, text: str) -> List[float]:
        """Vectoriza una consulta individual.

        Args:
            text: Texto de consulta.

        Returns:
            Vector de embeddings.
        """
        return self.model.embed_query(text)

