import importlib
import logging
import threading
from fastapi import HTTPException, Request, status

from app.application.processors.text_splitters.constants.text_splitter_type import TextSplitterType
from app.application.processors.text_splitters.exceptions.text_splitter_exception import (
    TextSplitterInitializationException,
    UnsupportedTextSplitterTypeException,
)
from app.application.processors.text_splitters.interfaces.text_splitter_interface import TextSplitterInterface
from app.application.processors.text_splitters.text_splitter_settings import TextSplitterSettings

logger = logging.getLogger(__name__)

_TEXT_SPLITTER_REGISTRY: dict[TextSplitterType, str] = {
    TextSplitterType.recursive: (
        "app.application.processors.text_splitters.instances"
        ".recursive_text_splitter.RecursiveTextSplitter"
    ),
    TextSplitterType.huggingface: (
        "app.application.processors.text_splitters.instances"
        ".huggingface_text_splitter.HuggingFaceTextSplitter"
    ),
}


def _import_splitter_class(
        dotted_path: str
) -> type[TextSplitterInterface]:
    module_path, class_name = dotted_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


class TextSplitterFactory:
    def __init__(
            self,
            text_splitter_settings: TextSplitterSettings | None = None
    ) -> None:
        self._settings = text_splitter_settings or TextSplitterSettings()
        self._active_type = self._settings.active_type

        self._lock = threading.Lock()
        self._splitter: TextSplitterInterface | None = None
        self._instances: dict[TextSplitterType, TextSplitterInterface] = {}

        logger.info(
            "The text splitter factory was created.",
            extra={
                "active_type": self._active_type,
                "available_types": [t.value for t in _TEXT_SPLITTER_REGISTRY]
            }
        )

    @property
    def splitter(
            self
    ) -> TextSplitterInterface:
        if self._splitter is not None:
            return self._splitter

        with self._lock:
            if self._splitter is None:
                self._splitter = self._build_splitter()

        return self._splitter

    def get_by_type(
            self,
            splitter_type: TextSplitterType
    ) -> TextSplitterInterface:
        if splitter_type not in _TEXT_SPLITTER_REGISTRY:
            raise UnsupportedTextSplitterTypeException("That text splitter type is not supported.")

        if splitter_type in self._instances:
            return self._instances[splitter_type]

        with self._lock:
            if splitter_type not in self._instances:
                self._instances[splitter_type] = self._build_by_type(splitter_type)

        return self._instances[splitter_type]

    def get_active_type(
            self
    ) -> TextSplitterType:
        return self._active_type

    def is_supported(
            self,
            splitter_type: TextSplitterType
    ) -> bool:
        return splitter_type in _TEXT_SPLITTER_REGISTRY

    def available_types(
            self
    ) -> list[TextSplitterType]:
        return list(_TEXT_SPLITTER_REGISTRY.keys())

    def _build_splitter(
            self
    ) -> TextSplitterInterface:
        if self._active_type not in _TEXT_SPLITTER_REGISTRY:
            raise UnsupportedTextSplitterTypeException("That text splitter type is not supported.")

        dotted_path = _TEXT_SPLITTER_REGISTRY[self._active_type]

        try:
            splitter_class = _import_splitter_class(dotted_path)
            instance = splitter_class(text_splitter_settings=self._settings)
            logger.info(
                "The text splitter was initialized and cached.",
                extra={
                    "splitter_type": self._active_type
                }
            )
            return instance
        except TextSplitterInitializationException:
            raise
        except Exception as e:
            logger.error(
                "An unexpected error occurred while initializing the text splitter.",
                extra={
                    "splitter_type": self._active_type,
                    "exception_type": type(e).__name__
                }
            )
            raise TextSplitterInitializationException("Failed to initialize the text splitter.") from e

    def _build_by_type(
            self,
            splitter_type: TextSplitterType
    ) -> TextSplitterInterface:
        dotted_path = _TEXT_SPLITTER_REGISTRY[splitter_type]

        try:
            splitter_class = _import_splitter_class(dotted_path)
            instance = splitter_class(text_splitter_settings=self._settings)
            logger.info(
                "The text splitter was initialized.",
                extra={
                    "splitter_type": splitter_type
                }
            )
            return instance
        except TextSplitterInitializationException:
            raise
        except Exception as e:
            logger.error(
                "An unexpected error occurred while initializing the text splitter.",
                extra={
                    "splitter_type": splitter_type,
                    "exception_type": type(e).__name__
                }
            )
            raise TextSplitterInitializationException("Failed to initialize the text splitter.") from e


async def get_text_splitter_factory(
        request: Request
) -> TextSplitterFactory:
    factory = getattr(request.app.state, "text_splitter_factory", None)
    if factory is None:
        logger.error("The text splitter factory was not registered on the application state.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Text splitter factory is not configured"
        )
    return factory
