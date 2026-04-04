import importlib
import logging
from functools import cached_property
from fastapi import HTTPException, Request, status

from app.application.processors.embedders.constants.embedder_type import EmbedderType
from app.application.processors.embedders.embedder_settings import EmbedderSettings
from app.application.processors.embedders.exceptions.embedder_exception import (
    EmbedderInitializationException,
    UnsupportedEmbedderTypeException
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


def _import_embedder_class(dotted_path: str) -> type[EmbedderInterface]:
    module_path, class_name = dotted_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls


class EmbedderFactory:
    def __init__(self, embedder_settings: EmbedderSettings | None = None) -> None:
        self._settings = embedder_settings or EmbedderSettings()
        self._active_type = self._settings.active_type

        logger.info(
            "EmbedderFactory created",
            extra={
                "active_type": self._active_type,
                "available_types": [t.value for t in _EMBEDDER_REGISTRY]
            }
        )

    @cached_property
    def embedder(self) -> EmbedderInterface:
        if self._active_type not in _EMBEDDER_REGISTRY:
            raise UnsupportedEmbedderTypeException(
                f"Unsupported embedder type: '{self._active_type}'. "
                f"Available: {[t.value for t in _EMBEDDER_REGISTRY]}"
            )

        dotted_path = _EMBEDDER_REGISTRY[self._active_type]

        try:
            embedder_class = _import_embedder_class(dotted_path)
            instance = embedder_class(embedder_settings=self._settings)
            logger.info(
                "Embedder initialized and cached",
                extra={"type": self._active_type}
            )
            return instance
        except EmbedderInitializationException:
            raise
        except Exception as e:
            logger.error(
                "Unexpected error during embedder initialization",
                extra={"type": self._active_type, "error": str(e)}
            )
            raise EmbedderInitializationException(
                f"Failed to initialize embedder '{self._active_type}': {e}"
            ) from e

    def get_active_type(self) -> EmbedderType:
        return self._active_type

    def is_supported(self, embedder_type: EmbedderType) -> bool:
        return embedder_type in _EMBEDDER_REGISTRY

    def available_types(self) -> list[EmbedderType]:
        return list(_EMBEDDER_REGISTRY.keys())


async def get_embedder_factory(request: Request) -> EmbedderFactory:
    try:
        return request.app.state.embedder_factory
    except AttributeError:
        logger.error("EmbedderFactory not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="EmbedderFactory is not available"
        )
