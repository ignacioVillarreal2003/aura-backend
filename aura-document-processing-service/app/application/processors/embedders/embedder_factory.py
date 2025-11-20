from typing import Dict

from app.application.processors.embedders.huggingface_embedder import HuggingfaceEmbedder
from app.application.processors.embedders.interfaces.embedding_interface import EmbedderInterface
from app.application.processors.embedders.ollama_embedder import OllamaEmbedder
from app.application.processors.embedders.sentence_transformer_embedder import SentenceTransformerEmbedder
from app.application.processors.embedders.spacy_embedder import SpacyEmbedder


class EmbedderFactory:
    def __init__(self):
        self._embeddings: Dict[str, EmbedderInterface] = {
            "huggingface": HuggingfaceEmbedder(),
            "ollama": OllamaEmbedder(),
            "sentence_transformer": SentenceTransformerEmbedder(),
            "spacy": SpacyEmbedder()
        }

    def get_embedder(self,
                     method: str) -> EmbedderInterface:
        if method not in self._embeddings:
            raise ValueError(f"Método de embedders no soportado: {method}")
        return self._embeddings[method]
