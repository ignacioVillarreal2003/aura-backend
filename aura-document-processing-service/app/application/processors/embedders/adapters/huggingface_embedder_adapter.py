from langchain_huggingface import HuggingFaceEmbeddings

from app.application.exceptions.api_exceptions import EmbedderError
from app.application.processors.embedders.interfaces.embedding_interface import EmbedderInterface


class HuggingfaceEmbedderAdapter(EmbedderInterface):
    def __init__(self):
        try:
            self.embeddings_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2",
                                                          model_kwargs={"device": None})
        except Exception as e:
            raise EmbedderError(f"Error al inicializar HuggingfaceEmbedderAdapter: {str(e)}")

    def embed_documents(self,
                        texts: list[str]) -> list[list[float]]:
        try:
            return self.embeddings_model.embed_documents(texts)
        except Exception as e:
            raise EmbedderError(f"Error al generar embeddings de documentos con HuggingfaceEmbedderAdapter: {str(e)}")

    def embed_query(self,
                    text: str) -> list[float]:
        try:
            return self.embeddings_model.embed_query(text)
        except Exception as e:
            raise EmbedderError(f"Error al generar embeddings de documentos con HuggingfaceEmbedderAdapter: {str(e)}")
