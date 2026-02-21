from pathlib import Path
from typing import Type, Dict

from app.application.processors.readers.adapters.digital_pdf_reader_adapter import DigitalPDFReaderAdapter
from app.application.processors.readers.adapters.digital_docx_reader_adapter import DigitalDOCXReaderAdapter
from app.application.processors.readers.adapters.scanned_docx_reader_adapter import ScannedDOCXReaderAdapter
from app.application.processors.readers.exceptions.reader_exception import UnsupportedReaderError
from app.application.processors.readers.interfaces.reader_adapter_interface import DocumentReaderInterface
from app.application.processors.readers.adapters.scanned_pdf_reader_adapter import ScannedPDFReaderAdapter
from app.application.processors.readers.constants.reader_type import ReaderType


class ReaderFactory:
    def __init__(
            self
    ):
        self._readers: Dict[ReaderType, Type[DocumentReaderInterface]] = {
            ReaderType.digital_pdf: DigitalPDFReaderAdapter,
            ReaderType.scanned_pdf: ScannedPDFReaderAdapter,
            ReaderType.digital_docx: DigitalDOCXReaderAdapter,
            ReaderType.scanned_docx: ScannedDOCXReaderAdapter
        }
        self._instances: Dict[str, DocumentReaderInterface] = {}

    def _get_or_create_reader(
            self,
            type: ReaderType
    ) -> DocumentReaderInterface:
        if type not in self._instances:
            self._instances[type] = self._readers[type]()
        return self._instances[type]

    def get_reader(
            self,
            file_path: Path
    ) -> DocumentReaderInterface:
        for type in self._readers:
            reader = self._get_or_create_reader(type)
            try:
                if reader.can_handle(file_path):
                    return reader
            except Exception:
                continue

        raise UnsupportedReaderError()
