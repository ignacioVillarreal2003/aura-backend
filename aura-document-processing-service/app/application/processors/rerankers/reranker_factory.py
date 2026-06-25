import importlib
import logging
import threading

from app.application.processors.rerankers.constants.reranker_type import RerankerType
from app.application.processors.rerankers.exceptions.reranker_exception import (
    RerankerInitializationException,
    UnsupportedRerankerTypeException,
)
from app.application.processors.rerankers.interfaces.reranker_interface import RerankerInterface
from app.application.processors.rerankers.reranker_settings import RerankerSettings

logger = logging.getLogger(__name__)

_RERANKER_REGISTRY: dict[RerankerType, str] = {
    RerankerType.cross_encoder: (
        "app.application.processors.rerankers.instances"
        ".cross_encoder_reranker.CrossEncoderReranker"
    ),
}


def _import_reranker_class(dotted_path: str) -> type[RerankerInterface]:
    module_path, class_name = dotted_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


class RerankerFactory:
    def __init__(
            self,
            reranker_settings: RerankerSettings | None = None,
    ) -> None:
        self._settings = reranker_settings or RerankerSettings()
        self._active_type = self._settings.active_type

        self._lock = threading.Lock()
        self._reranker: RerankerInterface | None = None

        logger.info(
            "The reranker factory was created.",
            extra={
                "active_type": self._active_type,
                "available_types": [t.value for t in _RERANKER_REGISTRY],
            }
        )

    @property
    def reranker(self) -> RerankerInterface:
        if self._reranker is not None:
            return self._reranker

        with self._lock:
            if self._reranker is None:
                self._reranker = self._build_reranker()

        return self._reranker

    def _build_reranker(self) -> RerankerInterface:
        if self._active_type not in _RERANKER_REGISTRY:
            raise UnsupportedRerankerTypeException("That reranker type is not supported.")

        dotted_path = _RERANKER_REGISTRY[self._active_type]

        try:
            reranker_class = _import_reranker_class(dotted_path)
            instance = reranker_class(reranker_settings=self._settings)
            logger.info(
                "The reranker was initialized and cached.",
                extra={"reranker_type": self._active_type}
            )
            return instance
        except RerankerInitializationException:
            raise
        except Exception as e:
            logger.error(
                "An unexpected error occurred while initializing the reranker.",
                extra={
                    "reranker_type": self._active_type,
                    "exception_type": type(e).__name__,
                }
            )
            raise RerankerInitializationException("Failed to initialize the reranker.") from e
