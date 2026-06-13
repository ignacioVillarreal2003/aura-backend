import importlib
import logging
import threading

from app.application.processors.embedders.constants.embedder_type import EmbedderType
from app.application.processors.embedders.embedder_settings import EmbedderSettings
from app.application.processors.embedders.exceptions.embedder_exception import (
    EmbedderInitializationException,
    UnsupportedEmbedderTypeException,
)
from app.application.processors.embedders.interfaces.embedder_interface import EmbedderInterface

logger = logging.getLogger(__name__)

_EMBEDDER_REGISTRY: dict[EmbedderType, str] = {
    EmbedderType.ollama: (
        "app.application.processors.embedders.instances"
        ".ollama_embedder.OllamaEmbedder"
    ),
    EmbedderType.huggingface: (
        "app.application.processors.embedders.instances"
        ".huggingface_embedder.HuggingFaceEmbedder"
    )
}


def _import_embedder_class(
        dotted_path: str
) -> type[EmbedderInterface]:
    module_path, class_name = dotted_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls


class EmbedderFactory:
    def __init__(
            self,
            embedder_settings: EmbedderSettings | None = None
    ) -> None:
        self._settings = embedder_settings or EmbedderSettings()
        self._active_type = self._settings.active_type

        self._lock = threading.Lock()
        self._embedder: EmbedderInterface | None = None
        self._instances: dict[EmbedderType, EmbedderInterface] = {}

        logger.info(
            "The embedder factory was created.",
            extra={
                "active_type": self._active_type,
                "available_types": [t.value for t in _EMBEDDER_REGISTRY]
            }
        )

    @property
    def embedder(
            self
    ) -> EmbedderInterface:
        if self._embedder is not None:
            return self._embedder

        with self._lock:
            if self._embedder is None:
                self._embedder = self._build_embedder()

        return self._embedder

    def get_by_type(
            self,
            embedder_type: EmbedderType
    ) -> EmbedderInterface:
        if embedder_type not in _EMBEDDER_REGISTRY:
            raise UnsupportedEmbedderTypeException("That embedder type is not supported.")

        if embedder_type in self._instances:
            return self._instances[embedder_type]

        with self._lock:
            if embedder_type not in self._instances:
                self._instances[embedder_type] = self._build_by_type(embedder_type)

        return self._instances[embedder_type]

    def get_active_type(
            self
    ) -> EmbedderType:
        return self._active_type

    def is_supported(
            self,
            embedder_type: EmbedderType
    ) -> bool:
        return embedder_type in _EMBEDDER_REGISTRY

    def available_types(
            self
    ) -> list[EmbedderType]:
        return list(_EMBEDDER_REGISTRY.keys())

    def _build_embedder(
            self
    ) -> EmbedderInterface:
        if self._active_type not in _EMBEDDER_REGISTRY:
            raise UnsupportedEmbedderTypeException("That embedder type is not supported.")

        dotted_path = _EMBEDDER_REGISTRY[self._active_type]

        try:
            embedder_class = _import_embedder_class(dotted_path)
            instance = embedder_class(embedder_settings=self._settings)
            logger.info(
                "The embedder was initialized and cached.",
                extra={
                    "embedder_type": self._active_type
                }
            )
            return instance
        except EmbedderInitializationException:
            raise
        except Exception as e:
            logger.error(
                "An unexpected error occurred while initializing the embedder.",
                extra={
                    "embedder_type": self._active_type,
                    "exception_type": type(e).__name__
                }
            )
            raise EmbedderInitializationException(
                "Failed to initialize the embedder."
            ) from e

    def _build_by_type(
            self,
            embedder_type: EmbedderType
    ) -> EmbedderInterface:
        dotted_path = _EMBEDDER_REGISTRY[embedder_type]

        try:
            embedder_class = _import_embedder_class(dotted_path)
            instance = embedder_class(embedder_settings=self._settings)

            logger.info(
                "The embedder was initialized.",
                extra={
                    "embedder_type": embedder_type
                }
            )
            return instance

        except EmbedderInitializationException:
            raise
        except Exception as e:
            logger.error(
                "An unexpected error occurred while initializing the embedder.",
                extra={
                    "embedder_type": embedder_type,
                    "exception_type": type(e).__name__
                }
            )
            raise EmbedderInitializationException("Failed to initialize the embedder.") from e
