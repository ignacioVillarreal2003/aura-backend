from sentence_transformers import SentenceTransformer

from app.application.processors.embedders.interfaces.embedding_interface import EmbedderInterface


class SentenceTransformerEmbedder(EmbedderInterface):
    def __init__(self,
                 model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"):
        self.model_name = model
        self.model = SentenceTransformer(model_name_or_path=self.model_name)

    def embed_documents(self,
                        texts: list[str]) -> list[list[float]]:
        return self.model.encode(texts,
                                 convert_to_numpy=True).tolist()

    def embed_query(self,
                    text: str) -> list[float]:
        return self.model.encode(text,
                                 convert_to_numpy=True).tolist()
