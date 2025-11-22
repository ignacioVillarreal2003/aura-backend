from langchain_ollama import OllamaEmbeddings

from app.application.exceptions.api_exceptions import EmbedderError
from app.application.processors.embedders.interfaces.embedding_interface import EmbedderInterface


class OllamaEmbedderAdapter(EmbedderInterface):
    def __init__(self):
        try:
            self.model = OllamaEmbeddings(model="nomic-embed-text:v1.5")
        except Exception as e:
            raise EmbedderError(f"Error al inicializar OllamaEmbedderAdapter: {str(e)}")

    def embed_documents(self,
                        texts: list[str]) -> list[list[float]]:
        try:
            return self.model.embed_documents(texts)
        except Exception as e:
            raise EmbedderError(f"Error al generar embeddings de documentos con OllamaEmbedderAdapter: {str(e)}")

    def embed_query(self,
                    text: str) -> list[float]:
        try:
            return self.model.embed_query(text)
        except Exception as e:
            raise EmbedderError(f"Error al generar embeddings de documentos con OllamaEmbedderAdapter: {str(e)}")
