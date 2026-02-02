from langchain_ollama import OllamaEmbeddings

from app.application.processors.embedders.exceptions.embedder_exception import EmbedderError
from app.application.processors.embedders.interfaces.embedder_adapter_interface import EmbedderAdapterInterface
from app.configuration.environment_variables import environment_variables


class OllamaEmbedderAdapter(EmbedderAdapterInterface):
    def __init__(
            self
    ):
        try:
            self.model = OllamaEmbeddings(
                model="nomic-embed-text:v1.5",
                base_url=environment_variables.ollama_base_url
            )
        except Exception as e:
            raise EmbedderError(f"Error al inicializar OllamaEmbedderAdapter: {str(e)}")

    def embed_documents(
            self,
            texts: list[str]
    ) -> list[list[float]]:
        try:
            return self.model.embed_documents(texts)
        except Exception as e:
            raise EmbedderError(f"Error al generar embeddings de documentos con OllamaEmbedderAdapter: {str(e)}")

    def embed_query(
            self,
            text: str
    ) -> list[float]:
        try:
            return self.model.embed_query(text)
        except Exception as e:
            raise EmbedderError(f"Error al generar embeddings de documentos con OllamaEmbedderAdapter: {str(e)}")
