from langchain_huggingface import HuggingFaceEmbeddings

from app.application.processors.embedders.interfaces.embedding_interface import EmbedderInterface


class HuggingfaceEmbedder(EmbedderInterface):
    def __init__(self,
                 model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
                 device: str | None = None):
        self.embeddings_model = HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs={"device": device}
        )

    def embed_documents(self,
                        texts: list[str]) -> list[list[float]]:
        return self.embeddings_model.embed_documents(texts)

    def embed_query(self,
                    text: str) -> list[float]:
        return self.embeddings_model.embed_query(text)
