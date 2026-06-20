import importlib
import logging
import threading

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
    )
}


def _import_cleaner_class(
        dotted_path: str
) -> type[TextCleanerInterface]:
    module_path, class_name = dotted_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls


class TextCleanerFactory:
    def __init__(
            self,
            text_cleaner_settings: TextCleanerSettings | None = None
    ) -> None:
        self._settings = text_cleaner_settings or TextCleanerSettings()
        self._active_type = self._settings.active_type

        self._lock = threading.Lock()
        self._cleaner: TextCleanerInterface | None = None

        logger.info(
            "The text cleaner factory was created.",
            extra={
                "active_type": self._active_type,
                "available_types": [t.value for t in _TEXT_CLEANER_REGISTRY]
            }
        )

    @property
    def cleaner(
            self
    ) -> TextCleanerInterface:
        if self._cleaner is not None:
            return self._cleaner

        with self._lock:
            if self._cleaner is None:
                self._cleaner = self._build_cleaner()

        return self._cleaner

    def get_active_type(
            self
    ) -> TextCleanerType:
        return self._active_type

    def _build_cleaner(
            self
    ) -> TextCleanerInterface:
        if self._active_type not in _TEXT_CLEANER_REGISTRY:
            raise UnsupportedTextCleanerTypeException("That text cleaner type is not supported.")

        dotted_path = _TEXT_CLEANER_REGISTRY[self._active_type]

        try:
            cleaner_class = _import_cleaner_class(dotted_path)
            instance = cleaner_class(text_cleaner_settings=self._settings)
            logger.info(
                "The text cleaner was initialized and cached.",
                extra={
                    "cleaner_type": self._active_type
                }
            )
            return instance
        except TextCleanerInitializationException:
            raise
        except Exception as e:
            logger.error(
                "An unexpected error occurred while initializing the text cleaner.",
                extra={
                    "cleaner_type": self._active_type,
                    "exception_type": type(e).__name__
                }
            )
            raise TextCleanerInitializationException("Failed to initialize the text cleaner.") from e
