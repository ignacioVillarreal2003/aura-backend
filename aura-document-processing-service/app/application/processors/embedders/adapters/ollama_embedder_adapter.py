import logging

from langchain_ollama import OllamaEmbeddings

from app.application.processors.embedders.exceptions.embedder_exception import (
    EmbedderInitializationException,
    EmbedDocumentsException,
    EmbedQueryException,
)
from app.application.processors.embedders.interfaces.embedder_adapter_interface import EmbedderAdapterInterface
from app.configuration.environment_variables import environment_variables

logger = logging.getLogger(__name__)

_EMBEDDER_NAME = "OllamaEmbedderAdapter"


class OllamaEmbedderAdapter(EmbedderAdapterInterface):
    def __init__(
            self
    ):
        try:
            self.model = OllamaEmbeddings(
                model="nomic-embed-text:v1.5",
                base_url=environment_variables.ollama_base_url
            )
            logger.info(
                f"OllamaEmbedderAdapter initialized [model=nomic-embed-text:v1.5, base_url={environment_variables.ollama_base_url}]"
            )
        except Exception as e:
            raise EmbedderInitializationException(_EMBEDDER_NAME, e)

    def embed_documents(
            self,
            texts: list[str]
    ) -> list[list[float]]:
        logger.info(f"Generating document embeddings [count={len(texts)}]")
        try:
            embeddings = self.model.embed_documents(texts)
            logger.info(f"Document embeddings generated successfully [count={len(embeddings)}]")
            return embeddings
        except Exception as e:
            raise EmbedDocumentsException(_EMBEDDER_NAME, e)

    def embed_query(
            self,
            text: str
    ) -> list[float]:
        logger.info("Generating query embedding")
        try:
            embedding = self.model.embed_query(text)
            logger.info("Query embedding generated successfully")
            return embedding
        except Exception as e:
            raise EmbedQueryException(_EMBEDDER_NAME, e)
