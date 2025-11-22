from pathlib import Path
from typing import Type, Dict

from app.application.exceptions.api_exceptions import UnsupportedReaderError
from app.application.processors.readers.adapters.digital_pdf_reader_adapter import DigitalPDFReaderAdapter
from app.application.processors.readers.adapters.docx_reader_adapter import DOCXReaderAdapter
from app.application.processors.readers.interfaces.document_reader_interface import DocumentReaderInterface
from app.application.processors.readers.adapters.scanned_pdf_reader_adapter import ScannedPDFReaderAdapter


class ReaderFactory:
    def __init__(self):
        self._readers: Dict[str, Type[DocumentReaderInterface]] = {
            "digital_pdf": DigitalPDFReaderAdapter,
            "scanned_pdf": ScannedPDFReaderAdapter,
            "docx": DOCXReaderAdapter
        }
        self._instances: Dict[str, DocumentReaderInterface] = {}

    def _get_or_create_reader(self,
                              key: str) -> DocumentReaderInterface:
        if key not in self._instances:
            self._instances[key] = self._readers[key]()
        return self._instances[key]

    def get_reader(self,
                   file_path: Path) -> DocumentReaderInterface:
        for key in self._readers:
            reader = self._get_or_create_reader(key)
            try:
                if reader.can_handle(file_path):
                    return reader
            except Exception:
                continue

        raise UnsupportedReaderError()
