import logging
import os
import platform
import shutil
from pathlib import Path
from typing import Optional
from fastapi import HTTPException, Request, status

from app.application.processors.readers.instances.digital_docx_reader import DigitalDOCXReader
from app.application.processors.readers.instances.digital_pdf_reader import DigitalPDFReader
from app.application.processors.readers.instances.scanned_docx_reader import ScannedDOCXReader
from app.application.processors.readers.instances.scanned_pdf_reader import ScannedPDFReader
from app.application.processors.readers.constants.reader_type import ReaderType
from app.application.processors.readers.exceptions.reader_exception import (
    ReaderException,
    UnsupportedReaderException
)
from app.application.processors.readers.interfaces.reader_interface import ReaderInterface
from app.application.processors.readers.reader_settings import ReaderSettings

logger = logging.getLogger(__name__)


class ReaderFactory:
    def __init__(
            self,
            reader_settings: Optional[ReaderSettings] = None
    ) -> None:
        self._reader_settings = reader_settings or ReaderSettings()

        self._reader_cache: dict[ReaderType, ReaderInterface] = {}

        self._tesseract_path: Optional[str] = self._resolve_tesseract()
        self._poppler_path: Optional[str] = self._resolve_poppler()

        self._initialize_readers()

    def get_reader(
            self,
            file_path: Path
    ) -> ReaderInterface:
        if not file_path.exists():
            raise ReaderException(f"File not found: {file_path}")

        logger.debug(
            "Finding reader for file",
            extra={
                "file": file_path.name
            }
        )

        reader_priority: list[ReaderType] = [
            ReaderType.digital_pdf,
            ReaderType.digital_docx,
            ReaderType.scanned_pdf,
            ReaderType.scanned_docx
        ]

        for reader_type in reader_priority:
            reader = self._reader_cache.get(reader_type)
            if not reader:
                continue

            try:
                if reader.can_handle(file_path):
                    logger.info(
                        "Reader selected",
                        extra={
                            "file": file_path.name,
                            "reader_type": reader_type
                        }
                    )
                    return reader
            except Exception as e:
                logger.debug(
                    "Reader cannot handle file",
                    extra={
                        "reader_type": reader_type,
                        "file": file_path.name,
                        "error": str(e)
                    }
                )

        logger.error(
            "No reader available for file",
            extra={
                "file_path": file_path
            }
        )
        raise UnsupportedReaderException(f"Unsupported reader for file: {file_path}")

    def is_supported(
            self,
            reader_type: ReaderType
    ) -> bool:
        return reader_type in self._reader_cache

    def get_supported_types(
            self
    ) -> list[ReaderType]:
        return list(self._reader_cache.keys())

    def _resolve_tesseract(
            self
    ) -> Optional[str]:
        if self._reader_settings.tesseract_path:
            if os.path.exists(self._reader_settings.tesseract_path):
                return self._reader_settings.tesseract_path
            logger.warning(
                "Configured tesseract path does not exist",
                extra={
                    "tesseract_path": self._reader_settings.tesseract_path
                }
            )

        found = shutil.which("tesseract")
        if found:
            logger.debug(
                "Auto-detected tesseract",
                extra={
                    "tesseract_path": found
                }
            )
            return found

        if platform.system() == "Windows":
            for tesseract_path in [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            ]:
                if os.path.exists(tesseract_path):
                    logger.debug(
                        "Found tesseract at default path",
                        extra={
                            "tesseract_path": tesseract_path
                        }
                    )
                    return tesseract_path

        return None

    def _resolve_poppler(
            self
    ) -> Optional[str]:
        if self._reader_settings.poppler_path:
            if os.path.exists(self._reader_settings.poppler_path):
                return self._reader_settings.poppler_path
            logger.warning(
                "Configured poppler path does not exist",
                extra={
                    "poppler_path": self._reader_settings.poppler_path
                }
            )

        if platform.system() == "Windows":
            for poppler_path in [
                r"C:\Program Files\poppler-25.07.0\Library\bin",
                r"C:\Program Files\poppler\Library\bin",
                r"C:\Program Files\poppler\bin",
                r"C:\poppler\Library\bin",
                r"C:\poppler\bin"
            ]:
                if os.path.exists(poppler_path):
                    logger.debug(
                        "Found poppler at default path",
                        extra={
                            "poppler_path": poppler_path
                        }
                    )
                    return poppler_path

        return None

    def _initialize_readers(
            self
    ) -> None:
        self._reader_cache[ReaderType.digital_pdf] = DigitalPDFReader()
        self._reader_cache[ReaderType.digital_docx] = DigitalDOCXReader()

        if not self._tesseract_path:
            logger.info("Skipping OCR readers — tesseract not available")
            return

        ocr_reader_settings = self._reader_settings.model_copy(
            update={
                "tesseract_path": self._tesseract_path,
                "poppler_path": self._poppler_path
            }
        )

        for reader_type, reader_class in [
            (ReaderType.scanned_docx, ScannedDOCXReader),
            (ReaderType.scanned_pdf, ScannedPDFReader)
        ]:
            try:
                self._reader_cache[reader_type] = reader_class(
                    reader_settings=ocr_reader_settings
                )
                logger.info(
                    "OCR reader initialized",
                    extra={
                        "reader_type": reader_type
                    }
                )
            except Exception as e:
                logger.error(
                    "Failed to initialize OCR reader",
                    extra={
                        "reader_type": reader_type,
                        "error": str(e)
                    }
                )


async def get_reader_factory(
        request: Request
) -> ReaderFactory:
    try:
        reader_factory: ReaderFactory = request.app.state.reader_factory
        return reader_factory
    except AttributeError:
        logger.error("ReaderFactory not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Reader factory not configured"
        )
