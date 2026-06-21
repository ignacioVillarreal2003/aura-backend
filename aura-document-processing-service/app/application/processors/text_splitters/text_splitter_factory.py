import importlib
import logging
import threading
from typing import Optional

from app.application.processors.text_splitters.constants.text_splitter_type import TextSplitterType
from app.application.processors.text_splitters.exceptions.text_splitter_exception import (
    TextSplitterInitializationException,
    TextSplitterUnavailableException,
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
    TextSplitterType.docling_hybrid: (
        "app.application.processors.text_splitters.instances"
        ".docling_hybrid_text_splitter.DoclingHybridTextSplitter"
    ),
}

_FLAT_TEXT_TYPES: frozenset[TextSplitterType] = frozenset({
    TextSplitterType.recursive,
    TextSplitterType.huggingface,
})


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
        self._instances: dict[TextSplitterType, TextSplitterInterface] = {}
        self._structured_unavailable = False

        logger.info(
            "The text splitter factory was created.",
            extra={
                "active_type": self._active_type,
                "available_types": [t.value for t in _TEXT_SPLITTER_REGISTRY]
            }
        )

    def get_active_type(
            self
    ) -> TextSplitterType:
        return self._active_type

    def warmup(
            self
    ) -> None:
        """Eagerly build the splitters needed at runtime so the first ingest does
        not pay the model-load cost.

        Always warms the flat-text (classic) splitter, which backs both the active
        flat-text type and the docling_hybrid fallback; a failure here is a real
        startup error and propagates. Also warms the structure-aware splitter when
        it is the active type, tolerant of Docling being unavailable (in which case
        ingestion falls back to the flat-text splitter).
        """
        self.get_classic_splitter()
        if self._active_type == TextSplitterType.docling_hybrid:
            self.get_structured_splitter()

    def get_structured_splitter(
            self
    ) -> Optional[TextSplitterInterface]:
        if self._active_type != TextSplitterType.docling_hybrid:
            return None
        if self._structured_unavailable:
            return None

        try:
            return self._get(TextSplitterType.docling_hybrid)
        except TextSplitterUnavailableException:
            self._structured_unavailable = True
            logger.warning(
                "Docling is unavailable; structural chunking is disabled and ingestion "
                "will fall back to the flat-text splitter."
            )
            return None
        except TextSplitterInitializationException:
            self._structured_unavailable = True
            logger.exception(
                "Failed to initialize the structural splitter; falling back to flat-text splitting."
            )
            return None

    def get_classic_type(
            self
    ) -> TextSplitterType:
        if self._active_type in _FLAT_TEXT_TYPES:
            return self._active_type
        return self._settings.structured_fallback_type

    def get_classic_splitter(
            self
    ) -> TextSplitterInterface:
        return self._get(self.get_classic_type())

    def _get(
            self,
            splitter_type: TextSplitterType
    ) -> TextSplitterInterface:
        if splitter_type not in _TEXT_SPLITTER_REGISTRY:
            raise UnsupportedTextSplitterTypeException("That text splitter type is not supported.")

        if splitter_type in self._instances:
            return self._instances[splitter_type]

        with self._lock:
            if splitter_type not in self._instances:
                self._instances[splitter_type] = self._build(splitter_type)

        return self._instances[splitter_type]

    def _build(
            self,
            splitter_type: TextSplitterType
    ) -> TextSplitterInterface:
        dotted_path = _TEXT_SPLITTER_REGISTRY[splitter_type]

        try:
            splitter_class = _import_splitter_class(dotted_path)
            instance = splitter_class(text_splitter_settings=self._settings)
            logger.info(
                "The text splitter was initialized and cached.",
                extra={
                    "splitter_type": splitter_type
                }
            )
            return instance
        except (TextSplitterInitializationException, TextSplitterUnavailableException):
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
