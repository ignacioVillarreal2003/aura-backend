from pathlib import Path
from docx import Document

from app.application.exceptions.api_exceptions import ReaderFileNotFoundError, UnsupportedDOCXFormatError, DOCXReadError
from app.application.processors.readers.interfaces.document_reader_interface import DocumentReaderInterface


class DOCXReaderAdapter(DocumentReaderInterface):
    def can_handle(self,
                   file_path: Path) -> bool:
        return file_path.suffix.lower() == ".docx"

    def read(self, file_path: Path) -> str:
        if not file_path.exists():
            raise ReaderFileNotFoundError(str(file_path))

        if not self.can_handle(file_path):
            raise UnsupportedDOCXFormatError(file_path.suffix)

        try:
            doc = Document(file_path)
            text_parts = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
            return "\n".join(text_parts)
        except Exception as e:
            raise DOCXReadError(str(file_path), e)
