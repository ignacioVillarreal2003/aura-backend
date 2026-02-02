from pathlib import Path
from docx import Document

from app.application.processors.readers.exceptions.reader_exception import (
    ReaderFileNotFoundError,
    UnsupportedDigitalDOCXFormatError,
    DigitalDOCXReadError,
    DOCXHasNoExtractableTextError
)
from app.application.processors.readers.interfaces.reader_adapter_interface import DocumentReaderInterface


class DigitalDOCXReaderAdapter(DocumentReaderInterface):
    def can_handle(
            self,
            file_path: Path
    ) -> bool:
        if file_path.suffix.lower() != ".docx":
            return False

        try:
            doc = Document(file_path)
            for paragraph in doc.paragraphs:
                if paragraph.text and paragraph.text.strip():
                    return True
            return False

        except Exception:
            return False

    def read(
            self,
            file_path: Path
    ) -> str:
        if not file_path.exists():
            raise ReaderFileNotFoundError(str(file_path))

        if not self.can_handle(file_path):
            raise UnsupportedDigitalDOCXFormatError(file_path.suffix)

        try:
            doc = Document(file_path)
            text_parts = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
            
            if not text_parts:
                raise DOCXHasNoExtractableTextError()
            
            return "\n".join(text_parts)
        except Exception as e:
            raise DigitalDOCXReadError(str(file_path), e)
