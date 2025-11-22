from typing import Dict, Type

from app.application.exceptions.api_exceptions import UnsupportedEmbedderMethodError
from app.application.processors.embedders.interfaces.embedding_interface import EmbedderInterface
from app.application.processors.embedders.adapters.huggingface_embedder_adapter import HuggingfaceEmbedderAdapter
from app.application.processors.embedders.adapters.ollama_embedder_adapter import OllamaEmbedderAdapter
from app.application.processors.embedders.adapters.sentence_transformer_embedder_adapter import \
    SentenceTransformerEmbedderAdapter
from app.application.processors.embedders.adapters.spacy_embedder_adapter import SpacyEmbedderAdapter


class EmbedderFactory:
    def __init__(self):
        self._embeddings: Dict[str, Type[EmbedderInterface]] = {
            "huggingface": HuggingfaceEmbedderAdapter,
            "ollama": OllamaEmbedderAdapter,
            "sentence_transformer": SentenceTransformerEmbedderAdapter,
            "spacy": SpacyEmbedderAdapter,
        }
        self._instances: Dict[str, EmbedderInterface] = {}

    def get_embedder(self,
                     method: str) -> EmbedderInterface:
        if method not in self._embeddings:
            raise UnsupportedEmbedderMethodError(method)

        if method not in self._instances:
            self._instances[method] = self._embeddings[method]()

        return self._instances[method]
