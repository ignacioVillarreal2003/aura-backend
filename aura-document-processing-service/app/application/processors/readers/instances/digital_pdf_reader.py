import logging
from pathlib import Path
import pypdf

from app.application.processors.readers.exceptions.reader_exception import (
    DigitalPDFReadException,
    PDFHasNoExtractableTextException,
    ReaderFileNotFoundException
)
from app.application.processors.readers.interfaces.reader_interface import ReaderInterface

logger = logging.getLogger(__name__)


class DigitalPDFReader(ReaderInterface):
    def can_handle(
            self,
            file_path: Path
    ) -> bool:
        if file_path.suffix.lower() != ".pdf":
            return False

        if not self._is_valid_pdf(file_path):
            return False

        try:
            with open(file_path, "rb") as file:
                pdf_reader = pypdf.PdfReader(file)

                if len(pdf_reader.pages) == 0:
                    return False

                pages_to_check = min(len(pdf_reader.pages), 3)
                for i in range(pages_to_check):
                    page_text = pdf_reader.pages[i].extract_text()
                    if page_text and page_text.strip():
                        return True

                return False

        except pypdf.errors.PdfReadError:
            logger.debug(
                "PDF read error during can_handle",
                extra={
                    "file": file_path.name
                }
            )
            return False
        except Exception as e:
            logger.debug(
                "Unexpected error during can_handle",
                extra={
                    "file": file_path.name,
                    "error": str(e)
                }
            )
            return False

    def read(
            self,
            file_path: Path
    ) -> str:
        if not file_path.exists():
            raise ReaderFileNotFoundException("The specified PDF file does not exist or cannot be accessed")

        logger.info(
            "Reading digital PDF",
            extra={
                "file": file_path.name
            }
        )

        text_parts = []
        total_pages = 0

        try:
            with open(file_path, "rb") as file:
                pdf_reader = pypdf.PdfReader(file)
                total_pages = len(pdf_reader.pages)

                for page_num in range(total_pages):
                    page = pdf_reader.pages[page_num]
                    page_text = page.extract_text()
                    if page_text and page_text.strip():
                        text_parts.append(page_text.strip())

            if not text_parts:
                raise PDFHasNoExtractableTextException(
                    "The PDF file does not contain extractable text. "
                    "It may be a scanned document requiring OCR."
                )

            logger.info(
                "Digital PDF read successfully",
                extra={
                    "file": file_path.name,
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
                "Unexpected error reading digital PDF",
                extra={
                    "file": file_path.name
                }
            )
            raise DigitalPDFReadException("An unexpected error occurred while reading the digital PDF file.") from e

    def _is_valid_pdf(
            self,
            file_path: Path
    ) -> bool:
        pdf_magic_numbers = [b"%PDF"]
        try:
            with open(file_path, "rb") as f:
                header = f.read(5)
                return any(header.startswith(magic) for magic in pdf_magic_numbers)
        except Exception as e:
            logger.debug(
                "Failed to validate PDF magic numbers",
                extra={
                    "file": file_path.name,
                    "error": str(e)
                }
            )
            return False
