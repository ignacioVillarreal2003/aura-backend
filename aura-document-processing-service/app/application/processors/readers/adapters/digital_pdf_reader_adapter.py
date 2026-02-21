import logging
from pathlib import Path

import pypdf

from app.application.processors.readers.exceptions.reader_exception import (
    ReaderFileNotFoundException,
    UnsupportedDigitalPDFFormatException,
    PDFHasNoExtractableTextException,
    DigitalPDFReadException
)
from app.application.processors.readers.interfaces.reader_adapter_interface import DocumentReaderInterface

logger = logging.getLogger(__name__)


class DigitalPDFReaderAdapter(DocumentReaderInterface):
    def can_handle(
            self,
            file_path: Path
    ) -> bool:
        if file_path.suffix.lower() != ".pdf":
            return False

        try:
            with open(file_path, "rb") as file:
                pdf_reader = pypdf.PdfReader(file)

                pages_to_check = min(len(pdf_reader.pages), 3)

                for i in range(pages_to_check):
                    page = pdf_reader.pages[i]
                    page_text = page.extract_text()

                    if page_text and page_text.strip():
                        return True
                return False

        except pypdf.Exceptions.PdfReadException:
            return False
        except Exception:
            return False

    def read(
            self,
            file_path: Path
    ) -> str:
        if not file_path.exists():
            raise ReaderFileNotFoundException(str(file_path))

        logger.info(f"Reading digital PDF [file={file_path.name}]")

        text_parts = []
        try:
            with open(file_path, "rb") as file:
                pdf_reader = pypdf.PdfReader(file)
                total_pages = len(pdf_reader.pages)

                for page_num, page in enumerate(pdf_reader.pages, 1):
                    page_text = page.extract_text()
                    if page_text and page_text.strip():
                        text_parts.append(page_text.strip())

            if not text_parts:
                raise PDFHasNoExtractableTextException()

            logger.info(
                f"Digital PDF read successfully [file={file_path.name}, pages={total_pages}, extracted={len(text_parts)}]"
            )
            return "\n\n".join(text_parts)

        except (ReaderFileNotFoundException, PDFHasNoExtractableTextException):
            raise
        except Exception as e:
            raise DigitalPDFReadException(str(file_path), e)
