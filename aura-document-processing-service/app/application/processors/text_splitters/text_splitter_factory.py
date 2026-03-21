import importlib
import logging
from functools import cached_property
from fastapi import HTTPException, Request, status

from app.application.processors.text_splitters.constants.text_splitter_type import TextSplitterType
from app.application.processors.text_splitters.exceptions.text_splitter_exception import (
    TextSplitterInitializationException,
    UnsupportedTextSplitterTypeException
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


def _import_splitter_class(dotted_path: str) -> type[TextSplitterInterface]:
    module_path, class_name = dotted_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


class TextSplitterFactory:
    def __init__(self, text_splitter_settings: TextSplitterSettings | None = None) -> None:
        self._settings = text_splitter_settings or TextSplitterSettings()
        self._active_type = self._settings.active_type

        logger.info(
            "TextSplitterFactory created",
            extra={
                "active_type": self._active_type,
                "available_types": [t.value for t in _TEXT_SPLITTER_REGISTRY]
            }
        )

    @cached_property
    def splitter(self) -> TextSplitterInterface:
        if self._active_type not in _TEXT_SPLITTER_REGISTRY:
            raise UnsupportedTextSplitterTypeException(
                f"Unsupported text splitter type: '{self._active_type}'. "
                f"Available: {[t.value for t in _TEXT_SPLITTER_REGISTRY]}"
            )

        dotted_path = _TEXT_SPLITTER_REGISTRY[self._active_type]

        try:
            splitter_class = _import_splitter_class(dotted_path)
            instance = splitter_class(text_splitter_settings=self._settings)
            logger.info(
                "Text splitter initialized and cached",
                extra={"type": self._active_type}
            )
            return instance
        except TextSplitterInitializationException:
            raise
        except Exception as e:
            logger.error(
                "Unexpected error during text splitter initialization",
                extra={"type": self._active_type, "error": str(e)}
            )
            raise TextSplitterInitializationException(
                f"Failed to initialize text splitter '{self._active_type}': {e}"
            ) from e

    def get_active_type(self) -> TextSplitterType:
        return self._active_type

    def is_supported(self, text_splitter_type: TextSplitterType) -> bool:
        return text_splitter_type in _TEXT_SPLITTER_REGISTRY

    def available_types(self) -> list[TextSplitterType]:
        return list(_TEXT_SPLITTER_REGISTRY.keys())


async def get_text_splitter_factory(request: Request) -> TextSplitterFactory:
    try:
        return request.app.state.text_splitter_factory
    except AttributeError:
        logger.error("TextSplitterFactory not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TextSplitterFactory is not available"
        )
