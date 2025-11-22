from pathlib import Path
import pypdf

from app.application.exceptions.api_exceptions import ReaderFileNotFoundError, UnsupportedDigitalPDFFormatError, \
    DigitalPDFReadError, PDFHasNoExtractableTextError
from app.application.processors.readers.interfaces.document_reader_interface import DocumentReaderInterface


class DigitalPDFReaderAdapter(DocumentReaderInterface):
    def can_handle(self,
                   file_path: Path) -> bool:
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

        except pypdf.errors.PdfReadError:
            return False
        except Exception:
            return False

    def read(self,
             file_path: Path) -> str:
        if not file_path.exists():
            raise ReaderFileNotFoundError(str(file_path))

        if not self.can_handle(file_path):
            raise UnsupportedDigitalPDFFormatError(file_path.suffix)

        text_parts = []
        try:
            with open(file_path, "rb") as file:
                pdf_reader = pypdf.PdfReader(file)
                for page_num, page in enumerate(pdf_reader.pages, 1):
                    page_text = page.extract_text()

                    if page_text and page_text.strip():
                        text_parts.append(page_text.strip())

            if not text_parts:
                raise PDFHasNoExtractableTextError()

            return "\n\n".join(text_parts)

        except Exception as e:
            raise DigitalPDFReadError(str(file_path), e)
