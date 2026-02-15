from typing import Dict, Type

from app.application.processors.embedders.adapters.ollama_embedder_adapter import OllamaEmbedderAdapter
from app.application.processors.embedders.exceptions.embedder_exception import UnsupportedEmbedderMethodError
from app.application.processors.embedders.interfaces.embedder_adapter_interface import EmbedderAdapterInterface
from app.application.processors.embedders.constants.embedder_type import EmbedderType


class EmbedderFactory:
    def __init__(
            self
    ):
        self._embeddings: Dict[EmbedderType, Type[EmbedderAdapterInterface]] = {
            EmbedderType.ollama: OllamaEmbedderAdapter
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
