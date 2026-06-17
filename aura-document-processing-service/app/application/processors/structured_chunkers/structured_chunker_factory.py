import logging
import threading
from typing import Optional

from app.application.processors.structured_chunkers.exceptions.structured_chunker_exception import (
    StructuredChunkerUnavailableException,
)
from app.application.processors.structured_chunkers.interfaces.structured_chunker_interface import (
    StructuredChunkerInterface,
)
from app.application.processors.structured_chunkers.structured_chunker_settings import (
    StructuredChunkerSettings,
)

logger = logging.getLogger(__name__)


class StructuredChunkerFactory:
    """Lazily builds the Docling hybrid chunker.

    Construction is deferred (it loads heavy Docling/tokenizer models) and tolerant:
    if Docling is not installed the factory reports the chunker as unavailable so the
    ingestion pipeline can fall back to the flat-text splitters.
    """

    def __init__(self, settings: Optional[StructuredChunkerSettings] = None) -> None:
        self._settings = settings or StructuredChunkerSettings()
        self._lock = threading.Lock()
        self._chunker: Optional[StructuredChunkerInterface] = None
        self._unavailable = False

    def get_chunker(self) -> Optional[StructuredChunkerInterface]:
        if self._chunker is not None:
            return self._chunker
        if self._unavailable:
            return None

        with self._lock:
            if self._chunker is None and not self._unavailable:
                self._chunker = self._build()

        return self._chunker

    def _build(self) -> Optional[StructuredChunkerInterface]:
        from app.application.processors.structured_chunkers.instances.docling_hybrid_chunker import (
            DoclingHybridChunker,
        )

        try:
            instance = DoclingHybridChunker(settings=self._settings)
            logger.info("The structured chunker was initialized and cached.")
            return instance
        except StructuredChunkerUnavailableException:
            self._unavailable = True
            logger.warning(
                "Docling is unavailable; structured chunking is disabled and ingestion "
                "will fall back to the flat-text splitters."
            )
            return None
        except Exception:
            self._unavailable = True
            logger.exception(
                "Failed to initialize the structured chunker; falling back to flat-text splitters."
            )
            return None
