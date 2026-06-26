import logging
import os
import platform
import shutil
from pathlib import Path
from typing import Optional

from app.application.processors.readers.constants.reader_type import ReaderType
from app.application.processors.readers.exceptions.reader_exception import (
    ReaderFileNotFoundException,
    ReaderInitializationException,
)
from app.application.processors.readers.interfaces.reader_interface import ReaderInterface
from app.application.processors.readers.reader_settings import ReaderSettings

logger = logging.getLogger(__name__)

_BASE_READER_PRIORITY: list[ReaderType] = [
    ReaderType.digital_pdf,
    ReaderType.digital_docx,
    ReaderType.scanned_pdf,
    ReaderType.scanned_docx,
    ReaderType.plain_text,
    ReaderType.csv,
]

_WINDOWS_TESSERACT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"
]
_WINDOWS_POPPLER_PATHS = [
    r"C:\Program Files\poppler-25.07.0\Library\bin",
    r"C:\Program Files\poppler\Library\bin",
    r"C:\Program Files\poppler\bin",
    r"C:\poppler\Library\bin",
    r"C:\poppler\bin"
]


class ReaderFactory:
    def __init__(
            self,
            reader_settings: Optional[ReaderSettings] = None
    ) -> None:
        self._settings = reader_settings or ReaderSettings()
        self._reader_cache: dict[ReaderType, ReaderInterface] = {}
        self._docling_lazy_failed: bool = False

        resolved_tesseract = self._resolve_tesseract()
        resolved_poppler = self._resolve_poppler()

        self._ocr_settings = self._settings.model_copy(
            update={
                "tesseract_path": resolved_tesseract,
                "poppler_path": resolved_poppler
            }
        )

        self._reader_priority = self._build_priority_list()

        self._initialize_readers()

        logger.info(
            "The reader factory was initialized.",
            extra={
                "registered_readers": [t.value for t in self._reader_cache],
                "reader_priority": [t.value for t in self._reader_priority],
                "ocr_available": self._ocr_settings.ocr_enabled,
                "docling_enabled": self._settings.docling_enabled
            }
        )

    def get_capable_readers(
            self,
            file_path: Path,
            *,
            prefer_docling: bool = False
    ) -> list[ReaderInterface]:
        if not file_path.exists():
            raise ReaderFileNotFoundException("The file was not found.")

        if prefer_docling:
            self._ensure_docling_reader()

        priority = self._effective_reader_priority(
            prefer_docling=prefer_docling
        )

        logger.debug(
            "Collecting capable readers for the file.",
            extra={
                "file_name": file_path.name,
                "prefer_docling": prefer_docling
            }
        )

        capable: list[ReaderInterface] = []
        for reader_type in priority:
            reader = self._reader_cache.get(reader_type)
            if reader is None:
                continue

            try:
                if reader.can_handle(file_path):
                    capable.append(reader)
            except Exception as e:
                logger.debug(
                    "The reader cannot handle this file.",
                    extra={
                        "reader_type": reader_type,
                        "file_name": file_path.name,
                        "exception_type": type(e).__name__
                    }
                )

        return capable

    def _build_priority_list(
            self
    ) -> list[ReaderType]:
        if self._settings.docling_enabled:
            return [ReaderType.docling, *_BASE_READER_PRIORITY]

        return [*_BASE_READER_PRIORITY, ReaderType.docling]

    def _effective_reader_priority(
            self,
            *,
            prefer_docling: bool
    ) -> list[ReaderType]:
        if not prefer_docling:
            return self._reader_priority
        return [ReaderType.docling] + [t for t in self._reader_priority if t != ReaderType.docling]

    def _ensure_docling_reader(
            self
    ) -> None:
        if ReaderType.docling in self._reader_cache:
            return
        if self._docling_lazy_failed:
            return

        try:
            from app.application.processors.readers.instances.docling_reader import DoclingReader
        except ImportError:
            self._docling_lazy_failed = True
            logger.warning(
                "Docling dependencies are not installed; prefer_docling will use the default reader order.",
            )
            return

        self._register(ReaderType.docling, DoclingReader, self._settings)
        if ReaderType.docling not in self._reader_cache:
            self._docling_lazy_failed = True
            logger.warning(
                "Lazy registration of the Docling reader failed; prefer_docling will use the default reader order.",
            )
        else:
            logger.info("The Docling reader was registered on demand for prefer_docling.")

    def _resolve_tesseract(
            self
    ) -> Optional[str]:
        if self._settings.tesseract_path:
            if os.path.exists(self._settings.tesseract_path):
                logger.debug(
                    "Using the configured Tesseract path.",
                    extra={
                        "path": self._settings.tesseract_path
                    }
                )
                return self._settings.tesseract_path
            logger.warning(
                "The configured Tesseract path does not exist.",
                extra={
                    "path": self._settings.tesseract_path
                }
            )

        found = shutil.which("tesseract")
        if found:
            logger.debug(
                "Tesseract was auto-detected on PATH.",
                extra={
                    "path": found
                }
            )
            return found

        if platform.system() == "Windows":
            for path in _WINDOWS_TESSERACT_PATHS:
                if os.path.exists(path):
                    logger.debug(
                        "Tesseract was found at a Windows default path.",
                        extra={
                            "path": path
                        }
                    )
                    return path

        logger.info("Tesseract was not found; OCR-based readers will be skipped.")
        return None

    def _resolve_poppler(
            self
    ) -> Optional[str]:
        if self._settings.poppler_path:
            if os.path.exists(self._settings.poppler_path):
                logger.debug(
                    "Using the configured Poppler path.",
                    extra={
                        "path": self._settings.poppler_path
                    }
                )
                return self._settings.poppler_path
            logger.warning(
                "The configured Poppler path does not exist.",
                extra={
                    "path": self._settings.poppler_path
                }
            )

        if platform.system() == "Windows":
            for path in _WINDOWS_POPPLER_PATHS:
                if os.path.exists(path):
                    logger.debug(
                        "Poppler was found at a Windows default path.",
                        extra={
                            "path": path
                        }
                    )
                    return path

        return None

    def _initialize_readers(
            self
    ) -> None:
        from app.application.processors.readers.instances.digital_pdf_reader import DigitalPDFReader
        from app.application.processors.readers.instances.digital_docx_reader import DigitalDOCXReader
        from app.application.processors.readers.instances.plain_text_reader import PlainTextReader
        from app.application.processors.readers.instances.csv_reader import CSVReader

        self._register(ReaderType.digital_pdf, DigitalPDFReader, self._settings)
        self._register(ReaderType.digital_docx, DigitalDOCXReader, self._settings)
        self._register(ReaderType.plain_text, PlainTextReader, self._settings)
        self._register(ReaderType.csv, CSVReader, self._settings)

        if self._settings.docling_enabled:
            try:
                from app.application.processors.readers.instances.docling_reader import DoclingReader
                self._register(ReaderType.docling, DoclingReader, self._settings)
            except ImportError:
                logger.warning(
                    "Docling is enabled but its dependencies are not installed; "
                    "skipping the Docling reader and using the default reader order."
                )

        if self._ocr_settings.ocr_enabled:
            from app.application.processors.readers.instances.scanned_pdf_reader import ScannedPDFReader
            from app.application.processors.readers.instances.scanned_docx_reader import ScannedDOCXReader

            self._register(ReaderType.scanned_pdf, ScannedPDFReader, self._ocr_settings)
            self._register(ReaderType.scanned_docx, ScannedDOCXReader, self._ocr_settings)
        else:
            logger.info(
                "Skipping Tesseract OCR readers because Tesseract is not available. "
                "Install tesseract-ocr or set READER_TESSERACT_PATH."
            )

    def _register(
            self,
            reader_type: ReaderType,
            reader_class: type,
            settings: ReaderSettings
    ) -> None:
        try:
            self._reader_cache[reader_type] = reader_class(reader_settings=settings)
            logger.debug(
                "A reader was registered.",
                extra={
                    "reader_type": reader_type
                }
            )
        except ReaderInitializationException as e:
            logger.error(
                "Failed to initialize a reader.",
                extra={
                    "reader_type": reader_type,
                    "exception_type": type(e).__name__
                }
            )
        except Exception as e:
            logger.error(
                "An unexpected error occurred while initializing a reader.",
                extra={
                    "reader_type": reader_type,
                    "exception_type": type(e).__name__
                }
            )
