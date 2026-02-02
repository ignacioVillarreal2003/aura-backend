from pathlib import Path
from typing import Type, Dict

from app.application.processors.readers.adapters.digital_pdf_reader_adapter import DigitalPDFReaderAdapter
from app.application.processors.readers.adapters.digital_docx_reader_adapter import DigitalDOCXReaderAdapter
from app.application.processors.readers.adapters.scanned_docx_reader_adapter import ScannedDOCXReaderAdapter
from app.application.processors.readers.exceptions.reader_exception import UnsupportedReaderError
from app.application.processors.readers.interfaces.reader_adapter_interface import DocumentReaderInterface
from app.application.processors.readers.adapters.scanned_pdf_reader_adapter import ScannedPDFReaderAdapter
from app.domain.constants.reader_type import ReaderType


class ReaderFactory:
    def __init__(
            self
    ):
        self._readers: Dict[ReaderType, Type[DocumentReaderInterface]] = {
            ReaderType.DIGITAL_PDF: DigitalPDFReaderAdapter,
            ReaderType.SCANNED_PDF: ScannedPDFReaderAdapter,
            ReaderType.DIGITAL_DOCX: DigitalDOCXReaderAdapter,
            ReaderType.SCANNED_DOCX: ScannedDOCXReaderAdapter
        }
        self._instances: Dict[str, DocumentReaderInterface] = {}

    def _get_or_create_reader(
            self,
            method: ReaderType
    ) -> DocumentReaderInterface:
        if method not in self._instances:
            self._instances[method] = self._readers[method]()
        return self._instances[method]

    def get_reader(
            self,
            file_path: Path
    ) -> DocumentReaderInterface:
        for method in self._readers:
            reader = self._get_or_create_reader(method)
            try:
                if reader.can_handle(file_path):
                    return reader
            except Exception:
                continue

        raise UnsupportedReaderError()
