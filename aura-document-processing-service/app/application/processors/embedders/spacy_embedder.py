import spacy

from app.application.processors.embedders.interfaces.embedding_interface import EmbedderInterface


class SpacyEmbedder(EmbedderInterface):
    def __init__(self,
                 model_name: str = "es_core_news_sm"):
        self.model_name = model_name
        self.nlp = spacy.load(self.model_name)

    def embed_documents(self,
                        texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            vectors.append(self.nlp(text).vector.tolist())
        return vectors

    def embed_query(self,
                    text: str) -> list[float]:
        return self.nlp(text).vector.tolist()
