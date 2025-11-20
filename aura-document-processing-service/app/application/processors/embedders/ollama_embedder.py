from langchain_ollama import OllamaEmbeddings

from app.application.processors.embedders.interfaces.embedding_interface import EmbedderInterface


class OllamaEmbedder(EmbedderInterface):
    def __init__(self,
                 model: str = "nomic-embed-text:v1.5"):
        self.model = OllamaEmbeddings(model=model)

    def embed_documents(self,
                        texts: list[str]) -> list[list[float]]:
        return self.model.embed_documents(texts)

    def embed_query(self,
                    text: str) -> list[float]:
        return self.model.embed_query(text)
