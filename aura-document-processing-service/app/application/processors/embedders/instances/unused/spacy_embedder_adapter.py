import spacy

from app.application.processors.embedders.exceptions.embedder_exception import (
    EmbedderInitializationException,
    EmbedDocumentsException,
    EmbedQueryException,
)
from app.application.processors.embedders.interfaces.embedder_interface import EmbedderAdapterInterface


class SpacyEmbedderAdapter(EmbedderAdapterInterface):
    def __init__(
            self
    ):
        try:
            self.nlp = spacy.load("es_core_news_sm")
        except Exception as e:
            raise EmbedderInitializationException("SpacyEmbedderAdapter", e)

    def embed_documents(
            self,
            texts: list[str]
    ) -> list[list[float]]:
        try:
            vectors = []
            for text in texts:
                vectors.append(self.nlp(text).vector.tolist())
            return vectors
        except Exception as e:
            raise EmbedDocumentsException("SpacyEmbedderAdapter", e)

    def embed_query(
            self,
            text: str
    ) -> list[float]:
        try:
            return self.nlp(text).vector.tolist()
        except Exception as e:
            raise EmbedQueryException("SpacyEmbedderAdapter", e)
