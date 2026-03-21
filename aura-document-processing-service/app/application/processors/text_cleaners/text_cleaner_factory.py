import importlib
import logging
from functools import cached_property
from fastapi import HTTPException, Request, status

from app.application.processors.text_cleaners.constants.text_cleaner_type import TextCleanerType
from app.application.processors.text_cleaners.exceptions.text_cleaner_exception import (
    TextCleanerInitializationException,
    UnsupportedTextCleanerTypeException
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


def _import_cleaner_class(dotted_path: str) -> type[TextCleanerInterface]:
    module_path, class_name = dotted_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


class TextCleanerFactory:
    def __init__(self, text_cleaner_settings: TextCleanerSettings | None = None) -> None:
        self._settings = text_cleaner_settings or TextCleanerSettings()
        self._active_type = self._settings.active_type

        logger.info(
            "TextCleanerFactory created",
            extra={
                "active_type": self._active_type,
                "available_types": [t.value for t in _TEXT_CLEANER_REGISTRY]
            }
        )

    @cached_property
    def cleaner(self) -> TextCleanerInterface:
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
                extra={"type": self._active_type}
            )
            return instance
        except TextCleanerInitializationException:
            raise
        except Exception as e:
            logger.error(
                "Unexpected error during text cleaner initialization",
                extra={"type": self._active_type, "error": str(e)}
            )
            raise TextCleanerInitializationException(
                f"Failed to initialize text cleaner '{self._active_type}': {e}"
            ) from e

    def get_active_type(self) -> TextCleanerType:
        return self._active_type

    def is_supported(self, text_cleaner_type: TextCleanerType) -> bool:
        return text_cleaner_type in _TEXT_CLEANER_REGISTRY

    def available_types(self) -> list[TextCleanerType]:
        return list(_TEXT_CLEANER_REGISTRY.keys())


async def get_text_cleaner_factory(request: Request) -> TextCleanerFactory:
    try:
        return request.app.state.text_cleaner_factory
    except AttributeError:
        logger.error("TextCleanerFactory not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TextCleanerFactory is not available"
        )
