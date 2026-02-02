from sentence_transformers import SentenceTransformer

from app.application.processors.embedders.exceptions.embedder_exception import EmbedderError
from app.application.processors.embedders.interfaces.embedder_adapter_interface import EmbedderAdapterInterface


class SentenceTransformerEmbedderAdapter(EmbedderAdapterInterface):
    def __init__(
            self
    ):
        try:
            self.model = SentenceTransformer(
                model_name_or_path="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
            )
        except Exception as e:
            raise EmbedderError(f"Error al inicializar SentenceTransformerEmbedderAdapter: {str(e)}")

    def embed_documents(
            self,
            texts: list[str]
    ) -> list[list[float]]:
        try:
            return self.model.encode(
                texts,
                convert_to_numpy=True
            ).tolist()
        except Exception as e:
            raise EmbedderError(
                f"Error al generar embeddings de documentos con SentenceTransformerEmbedderAdapter: {str(e)}"
            )

    def embed_query(
            self,
            text: str) -> list[float]:
        try:
            return self.model.encode(
                text,
                convert_to_numpy=True
            ).tolist()
        except Exception as e:
            raise EmbedderError(
                f"Error al generar embeddings de documentos con SentenceTransformerEmbedderAdapter: {str(e)}"
            )
