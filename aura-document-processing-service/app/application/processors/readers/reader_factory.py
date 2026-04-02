import logging
import os
import platform
import shutil
from pathlib import Path
from typing import Optional
from fastapi import HTTPException, Request, status

from app.application.processors.readers.constants.reader_type import ReaderType
from app.application.processors.readers.exceptions.reader_exception import (
    ReaderException,
    ReaderInitializationException,
    UnsupportedReaderException,
)
from app.application.processors.readers.interfaces.reader_interface import ReaderInterface
from app.application.processors.readers.reader_settings import ReaderSettings

logger = logging.getLogger(__name__)

_BASE_READER_PRIORITY: list[ReaderType] = [
    ReaderType.digital_pdf,
    ReaderType.digital_docx,
    ReaderType.scanned_pdf,
    ReaderType.scanned_docx,
]

_WINDOWS_TESSERACT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]
_WINDOWS_POPPLER_PATHS = [
    r"C:\Program Files\poppler-25.07.0\Library\bin",
    r"C:\Program Files\poppler\Library\bin",
    r"C:\Program Files\poppler\bin",
    r"C:\poppler\Library\bin",
    r"C:\poppler\bin",
]


class ReaderFactory:
    def __init__(self, reader_settings: Optional[ReaderSettings] = None) -> None:
        self._settings = reader_settings or ReaderSettings()
        self._reader_cache: dict[ReaderType, ReaderInterface] = {}
        self._docling_lazy_failed: bool = False

        resolved_tesseract = self._resolve_tesseract()
        resolved_poppler = self._resolve_poppler()

        self._ocr_settings = self._settings.model_copy(
            update={
                "tesseract_path": resolved_tesseract,
                "poppler_path": resolved_poppler,
            }
        )

        self._reader_priority = self._build_priority_list()

        self._initialize_readers()

        logger.info(
            "ReaderFactory initialized",
            extra={
                "registered_readers": [t.value for t in self._reader_cache],
                "reader_priority": [t.value for t in self._reader_priority],
                "ocr_available": self._ocr_settings.ocr_enabled,
                "docling_enabled": self._settings.docling_enabled,
            },
        )

    def get_reader(self, file_path: Path, *, prefer_docling: bool = False) -> ReaderInterface:
        if not file_path.exists():
            raise ReaderException(f"File not found: {file_path}")

        if prefer_docling:
            self._ensure_docling_reader()

        priority = self._effective_reader_priority(prefer_docling=prefer_docling)

        logger.debug(
            "Finding reader for file",
            extra={
                "file": file_path.name,
                "prefer_docling": prefer_docling,
            },
        )

        for reader_type in priority:
            reader = self._reader_cache.get(reader_type)
            if reader is None:
                continue

            try:
                if reader.can_handle(file_path):
                    logger.info(
                        "Reader selected",
                        extra={
                            "file": file_path.name,
                            "reader_type": reader_type,
                            "prefer_docling": prefer_docling,
                        },
                    )
                    return reader
            except Exception as e:
                logger.debug(
                    "Reader cannot handle file",
                    extra={
                        "reader_type": reader_type,
                        "file": file_path.name,
                        "error": str(e),
                    },
                )

        logger.error("No reader available for file", extra={"file": str(file_path)})
        raise UnsupportedReaderException(f"No reader found for file: {file_path.name}")

    def is_supported(self, reader_type: ReaderType) -> bool:
        return reader_type in self._reader_cache

    def available_types(self) -> list[ReaderType]:
        return list(self._reader_cache.keys())

    def _build_priority_list(self) -> list[ReaderType]:
        if self._settings.docling_enabled:
            return [ReaderType.docling] + _BASE_READER_PRIORITY

        return _BASE_READER_PRIORITY + [ReaderType.docling]

    def _effective_reader_priority(self, *, prefer_docling: bool) -> list[ReaderType]:
        if not prefer_docling:
            return self._reader_priority
        return [ReaderType.docling] + [
            t for t in self._reader_priority if t != ReaderType.docling
        ]

    def _ensure_docling_reader(self) -> None:
        if ReaderType.docling in self._reader_cache:
            return
        if self._docling_lazy_failed:
            return

        from app.application.processors.readers.instances.docling_reader import DoclingReader

        self._register(ReaderType.docling, DoclingReader, self._settings)
        if ReaderType.docling not in self._reader_cache:
            self._docling_lazy_failed = True
            logger.warning(
                "Lazy Docling registration failed — prefer_docling will fall back to default priority",
            )
        else:
            logger.info("Docling reader registered on demand for prefer_docling")

    def _resolve_tesseract(self) -> Optional[str]:
        if self._settings.tesseract_path:
            if os.path.exists(self._settings.tesseract_path):
                logger.debug(
                    "Using configured tesseract path",
                    extra={"path": self._settings.tesseract_path},
                )
                return self._settings.tesseract_path
            logger.warning(
                "Configured tesseract path does not exist",
                extra={"path": self._settings.tesseract_path},
            )

        found = shutil.which("tesseract")
        if found:
            logger.debug("Auto-detected tesseract on PATH", extra={"path": found})
            return found

        if platform.system() == "Windows":
            for path in _WINDOWS_TESSERACT_PATHS:
                if os.path.exists(path):
                    logger.debug(
                        "Found tesseract at Windows default path", extra={"path": path}
                    )
                    return path

        logger.info("Tesseract not found — OCR readers will be skipped")
        return None

    def _resolve_poppler(self) -> Optional[str]:
        if self._settings.poppler_path:
            if os.path.exists(self._settings.poppler_path):
                logger.debug(
                    "Using configured poppler path",
                    extra={"path": self._settings.poppler_path},
                )
                return self._settings.poppler_path
            logger.warning(
                "Configured poppler path does not exist",
                extra={"path": self._settings.poppler_path},
            )

        if platform.system() == "Windows":
            for path in _WINDOWS_POPPLER_PATHS:
                if os.path.exists(path):
                    logger.debug(
                        "Found poppler at Windows default path", extra={"path": path}
                    )
                    return path

        return None

    def _initialize_readers(self) -> None:
        from app.application.processors.readers.instances.digital.digital_pdf_reader import DigitalPDFReader
        from app.application.processors.readers.instances.digital.digital_docx_reader import DigitalDOCXReader

        self._register(ReaderType.digital_pdf, DigitalPDFReader, self._settings)
        self._register(ReaderType.digital_docx, DigitalDOCXReader, self._settings)

        if self._settings.docling_enabled:
            from app.application.processors.readers.instances.docling_reader import DoclingReader
            self._register(ReaderType.docling, DoclingReader, self._settings)

        if self._ocr_settings.ocr_enabled:
            from app.application.processors.readers.instances.scanned.scanned_pdf_reader import (
                ScannedPDFReader,
            )
            from app.application.processors.readers.instances.scanned.scanned_docx_reader import (
                ScannedDOCXReader,
            )

            self._register(ReaderType.scanned_pdf, ScannedPDFReader, self._ocr_settings)
            self._register(ReaderType.scanned_docx, ScannedDOCXReader, self._ocr_settings)
        else:
            logger.info(
                "Skipping Tesseract OCR readers — tesseract not available. "
                "Install tesseract-ocr or set READER_TESSERACT_PATH."
            )

    def _register(
            self,
            reader_type: ReaderType,
            reader_class: type,
            settings: ReaderSettings,
    ) -> None:
        try:
            self._reader_cache[reader_type] = reader_class(reader_settings=settings)
            logger.debug("Reader registered", extra={"reader_type": reader_type})
        except ReaderInitializationException as e:
            logger.error(
                "Failed to initialize reader",
                extra={"reader_type": reader_type, "error": str(e)},
            )
        except Exception as e:
            logger.error(
                "Unexpected error initializing reader",
                extra={"reader_type": reader_type, "error": str(e)},
            )


async def get_reader_factory(request: Request) -> ReaderFactory:
    try:
        return request.app.state.reader_factory
    except AttributeError:
        logger.error("ReaderFactory not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ReaderFactory is not available",
        )
