import logging
from pathlib import Path
from typing import Optional
import pypdf

from app.application.processors.readers.exceptions.reader_exception import (
    DigitalPDFReadException,
    PDFHasNoExtractableTextException,
    ReaderFileNotFoundException,
)
from app.application.processors.readers.instances.base_reader import BaseReader
from app.application.processors.readers.reader_settings import ReaderSettings

logger = logging.getLogger(__name__)

_CAN_HANDLE_PAGES_TO_PROBE = 3


class DigitalPDFReader(BaseReader):
    def __init__(
            self,
            reader_settings: Optional[ReaderSettings] = None
    ) -> None:
        self._settings = reader_settings or ReaderSettings()

        logger.info("The digital PDF reader was initialized successfully.")

    def can_handle(
            self,
            file_path: Path
    ) -> bool:
        if file_path.suffix.lower() != ".pdf":
            return False

        try:
            with open(file_path, "rb") as f:
                reader = pypdf.PdfReader(f)

                if len(reader.pages) == 0:
                    return False

                pages_to_probe = min(len(reader.pages), _CAN_HANDLE_PAGES_TO_PROBE)
                for i in range(pages_to_probe):
                    text = reader.pages[i].extract_text()
                    if text and text.strip():
                        return True

                return False

        except pypdf.errors.PdfReadError:
            logger.debug(
                "A PDF read error occurred while checking whether the file can be handled.",
                extra={
                    "file_name": file_path.name
                }
            )
            return False
        except Exception as e:
            logger.debug(
                "An unexpected error occurred while checking whether the PDF can be handled.",
                extra={
                    "file_name": file_path.name,
                    "exception_type": type(e).__name__
                }
            )
            return False

    def read(
            self,
            file_path: Path
    ) -> str:
        self._validate_file_exists(file_path)

        logger.info(
            "Reading a digital PDF.",
            extra={
                "file_name": file_path.name
            }
        )

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
                    "It may be a scanned document requiring OCR."
                )

            logger.info(
                "The digital PDF was read successfully.",
                extra={
                    "file_name": file_path.name,
                    "total_pages": total_pages,
                    "pages_with_text": len(text_parts)
                }
            )

            return "\n\n".join(text_parts)

        except (
                ReaderFileNotFoundException,
                PDFHasNoExtractableTextException
        ):
            raise
        except pypdf.errors.PdfReadError as e:
            raise DigitalPDFReadException("Failed to read the digital PDF file due to a parsing error.") from e
        except Exception as e:
            logger.exception(
                "An unexpected error occurred while reading the digital PDF.",
                extra={
                    "file_name": file_path.name
                }
            )
            raise DigitalPDFReadException("An unexpected error occurred while reading the digital PDF file.") from e
