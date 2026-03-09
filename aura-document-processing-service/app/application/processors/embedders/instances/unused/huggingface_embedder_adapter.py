from langchain_huggingface import HuggingFaceEmbeddings

from app.application.processors.embedders.exceptions.embedder_exception import (
    EmbedderInitializationException,
    EmbedDocumentsException,
    EmbedQueryException,
)
from app.application.processors.embedders.interfaces.embedder_interface import EmbedderAdapterInterface


class HuggingfaceEmbedderAdapter(EmbedderAdapterInterface):
    def __init__(
            self
    ):
        try:
            self.embeddings_model = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                model_kwargs={
                    "device": None
                }
            )
        except Exception as e:
            raise EmbedderInitializationException("HuggingfaceEmbedderAdapter", e)

    def embed_documents(
            self,
            texts: list[str]
    ) -> list[list[float]]:
        try:
            return self.embeddings_model.embed_documents(texts)
        except Exception as e:
            raise EmbedDocumentsException("HuggingfaceEmbedderAdapter", e)

    def embed_query(
            self,
            text: str
    ) -> list[float]:
        try:
            return self.embeddings_model.embed_query(text)
        except Exception as e:
            raise EmbedQueryException("HuggingfaceEmbedderAdapter", e)
