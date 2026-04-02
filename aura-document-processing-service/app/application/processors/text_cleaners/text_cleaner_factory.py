import importlib
import logging
import threading
from fastapi import HTTPException, Request, status

from app.application.processors.text_cleaners.constants.text_cleaner_type import TextCleanerType
from app.application.processors.text_cleaners.exceptions.text_cleaner_exception import (
    TextCleanerInitializationException,
    UnsupportedTextCleanerTypeException,
)
from app.application.processors.text_cleaners.interfaces.text_cleaner_interface import TextCleanerInterface
from app.application.processors.text_cleaners.text_cleaner_settings import TextCleanerSettings

logger = logging.getLogger(__name__)

_TEXT_CLEANER_REGISTRY: dict[TextCleanerType, str] = {
    TextCleanerType.simple: (
        "app.application.processors.text_cleaners.instances"
        ".simple_text_cleaner.SimpleTextCleaner"
    ),
}


def _import_cleaner_class(dotted_path: str) -> type[TextCleanerInterface]:
    module_path, class_name = dotted_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls


class TextCleanerFactory:
    def __init__(self, text_cleaner_settings: TextCleanerSettings | None = None) -> None:
        self._settings = text_cleaner_settings or TextCleanerSettings()
        self._active_type = self._settings.active_type

        self._lock = threading.Lock()
        self._cleaner: TextCleanerInterface | None = None
        self._instances: dict[TextCleanerType, TextCleanerInterface] = {}

        logger.info(
            "TextCleanerFactory created",
            extra={
                "active_type": self._active_type,
                "available_types": [t.value for t in _TEXT_CLEANER_REGISTRY],
            },
        )

    @property
    def cleaner(self) -> TextCleanerInterface:
        if self._cleaner is not None:
            return self._cleaner

        with self._lock:
            if self._cleaner is None:
                self._cleaner = self._build_cleaner()

        return self._cleaner

    def get_by_type(self, cleaner_type: TextCleanerType) -> TextCleanerInterface:
        if cleaner_type not in _TEXT_CLEANER_REGISTRY:
            raise UnsupportedTextCleanerTypeException(
                f"Unsupported text cleaner type: '{cleaner_type}'. "
                f"Available: {[t.value for t in _TEXT_CLEANER_REGISTRY]}"
            )

        if cleaner_type in self._instances:
            return self._instances[cleaner_type]

        with self._lock:
            if cleaner_type not in self._instances:
                self._instances[cleaner_type] = self._build_by_type(cleaner_type)

        return self._instances[cleaner_type]

    def get_active_type(self) -> TextCleanerType:
        return self._active_type

    def is_supported(self, text_cleaner_type: TextCleanerType) -> bool:
        return text_cleaner_type in _TEXT_CLEANER_REGISTRY

    def available_types(self) -> list[TextCleanerType]:
        return list(_TEXT_CLEANER_REGISTRY.keys())

    def _build_cleaner(self) -> TextCleanerInterface:
        if self._active_type not in _TEXT_CLEANER_REGISTRY:
            raise UnsupportedTextCleanerTypeException(
                f"Unsupported text cleaner type: '{self._active_type}'. "
                f"Available: {[t.value for t in _TEXT_CLEANER_REGISTRY]}"
            )

        dotted_path = _TEXT_CLEANER_REGISTRY[self._active_type]

        try:
            cleaner_class = _import_cleaner_class(dotted_path)
            instance = cleaner_class(text_cleaner_settings=self._settings)
            logger.info(
                "Text cleaner initialized and cached",
                extra={"type": self._active_type},
            )
            return instance
        except TextCleanerInitializationException:
            raise
        except Exception as e:
            logger.error(
                "Unexpected error during text cleaner initialization",
                extra={"type": self._active_type, "error": str(e)},
            )
            raise TextCleanerInitializationException(
                f"Failed to initialize text cleaner '{self._active_type}': {e}"
            ) from e

    def _build_by_type(self, cleaner_type: TextCleanerType) -> TextCleanerInterface:
        dotted_path = _TEXT_CLEANER_REGISTRY[cleaner_type]

        try:
            cleaner_class = _import_cleaner_class(dotted_path)
            instance = cleaner_class(text_cleaner_settings=self._settings)

            logger.info(
                "Text cleaner initialized",
                extra={"type": cleaner_type},
            )
            return instance

        except TextCleanerInitializationException:
            raise
        except Exception as e:
            logger.error(
                "Unexpected error during text cleaner initialization",
                extra={"type": cleaner_type, "error": str(e)},
            )
            raise TextCleanerInitializationException(
                f"Failed to initialize text cleaner '{cleaner_type}': {e}"
            ) from e


async def get_text_cleaner_factory(request: Request) -> TextCleanerFactory:
    try:
        return request.app.state.text_cleaner_factory
    except AttributeError:
        logger.error("TextCleanerFactory not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TextCleanerFactory is not available",
        )
