import logging
from pathlib import Path
from typing import Optional
import pypdf

from app.application.processors.readers.exceptions.reader_exception import (
    DigitalPDFReadException,
    PDFHasNoExtractableTextException,
    ReaderFileNotFoundException,
    ReaderInitializationException
)
from app.application.processors.readers.interfaces.reader_interface import ReaderInterface
from app.application.processors.readers.reader_settings import ReaderSettings

logger = logging.getLogger(__name__)


class DigitalPDFReader(ReaderInterface):
    _PDF_MAGIC = b"%PDF"
    _CAN_HANDLE_PAGES_TO_PROBE = 3

    def __init__(self, reader_settings: Optional[ReaderSettings] = None) -> None:
        self._settings = reader_settings or ReaderSettings()

        try:
            logger.info("DigitalPDFReader initialized successfully")
        except Exception as e:
            logger.exception("Failed to initialize DigitalPDFReader")
            raise ReaderInitializationException(
                f"DigitalPDFReader initialization failed: {e}"
            ) from e

    def can_handle(self, file_path: Path) -> bool:
        if file_path.suffix.lower() != ".pdf":
            return False

        if not self._is_valid_pdf(file_path):
            return False

        try:
            with open(file_path, "rb") as f:
                reader = pypdf.PdfReader(f)

                if len(reader.pages) == 0:
                    return False

                pages_to_probe = min(len(reader.pages), self._CAN_HANDLE_PAGES_TO_PROBE)
                for i in range(pages_to_probe):
                    text = reader.pages[i].extract_text()
                    if text and text.strip():
                        return True

                return False

        except pypdf.errors.PdfReadError:
            logger.debug("PDF read error during can_handle", extra={"file": file_path.name})
            return False
        except Exception as e:
            logger.debug("Unexpected error during can_handle", extra={"file": file_path.name, "error": str(e)})
            return False

    def read(self, file_path: Path) -> str:
        if not file_path.exists():
            raise ReaderFileNotFoundException(
                "The specified PDF file does not exist or cannot be accessed."
            )

        logger.info("Reading digital PDF", extra={"file": file_path.name})

        text_parts: list[str] = []
        total_pages = 0

        try:
            with open(file_path, "rb") as f:
                reader = pypdf.PdfReader(f)
                total_pages = len(reader.pages)

                for page_num in range(total_pages):
                    page_text = reader.pages[page_num].extract_text()
                    if page_text and page_text.strip():
                        text_parts.append(page_text.strip())

            if not text_parts:
                raise PDFHasNoExtractableTextException(
                    "The PDF file does not contain extractable text. "
                    "It may be a scanned document_controllers requiring OCR."
                )

            logger.info(
                "Digital PDF read successfully",
                extra={
                    "file": file_path.name,
                    "total_pages": total_pages,
                    "pages_with_text": len(text_parts),
                },
            )

            return "\n\n".join(text_parts)

        except (ReaderFileNotFoundException, PDFHasNoExtractableTextException):
            raise
        except pypdf.errors.PdfReadError as e:
            raise DigitalPDFReadException(
                "Failed to read the digital PDF file due to a parsing error."
            ) from e
        except Exception as e:
            logger.exception("Unexpected error reading digital PDF", extra={"file": file_path.name})
            raise DigitalPDFReadException(
                "An unexpected error occurred while reading the digital PDF file."
            ) from e

    def _is_valid_pdf(self, file_path: Path) -> bool:
        try:
            with open(file_path, "rb") as f:
                return f.read(5).startswith(self._PDF_MAGIC)
        except Exception as e:
            logger.debug("Failed to validate PDF magic bytes", extra={"file": file_path.name, "error": str(e)})
            return False
