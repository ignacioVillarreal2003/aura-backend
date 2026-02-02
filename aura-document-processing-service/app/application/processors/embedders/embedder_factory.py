from typing import Dict, Type

from app.application.processors.embedders.adapters.huggingface_embedder_adapter import HuggingfaceEmbedderAdapter
from app.application.processors.embedders.adapters.ollama_embedder_adapter import OllamaEmbedderAdapter
from app.application.processors.embedders.adapters.sentence_transformer_embedder_adapter import (
    SentenceTransformerEmbedderAdapter
)
from app.application.processors.embedders.adapters.spacy_embedder_adapter import SpacyEmbedderAdapter
from app.application.processors.embedders.exceptions.embedder_exception import UnsupportedEmbedderMethodError
from app.application.processors.embedders.interfaces.embedder_adapter_interface import EmbedderAdapterInterface
from app.domain.constants.embedder_type import EmbedderType


class EmbedderFactory:
    def __init__(
            self
    ):
        self._embeddings: Dict[EmbedderType, Type[EmbedderAdapterInterface]] = {
            EmbedderType.HUGGINGFACE: HuggingfaceEmbedderAdapter,
            EmbedderType.OLLAMA: OllamaEmbedderAdapter,
            EmbedderType.SENTENCE_TRANSFORMER: SentenceTransformerEmbedderAdapter,
            EmbedderType.SPACY: SpacyEmbedderAdapter,
        }
        self._instances: Dict[str, EmbedderAdapterInterface] = {}

    def get_embedder(
            self,
            method: EmbedderType
    ) -> EmbedderAdapterInterface:
        if method not in self._embeddings:
            raise UnsupportedEmbedderMethodError(method)

        if method not in self._instances:
            self._instances[method] = self._embeddings[method]()

        return self._instances[method]
