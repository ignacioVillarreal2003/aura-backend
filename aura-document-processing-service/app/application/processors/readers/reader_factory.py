from pathlib import Path
from typing import List

from app.application.processors.readers.digital_pdf_reader import DigitalPDFReader
from app.application.processors.readers.docx_reader import DOCXReader
from app.application.processors.readers.interfaces.document_reader_interface import DocumentReaderInterface
from app.application.processors.readers.scanned_pdf_reader import ScannedPDFReader


class ReaderFactory:
    def __init__(self):
        self._readers: List[DocumentReaderInterface] = [
            DigitalPDFReader(),
            ScannedPDFReader(),
            DOCXReader()
        ]

    def get_reader(self, file_path: Path) -> DocumentReaderInterface:
        for reader in self._readers:
            try:
                if reader.can_handle(file_path):
                    return reader
            except Exception:
                continue
        raise ValueError(f"No se encontró lector compatible para el archivo: {file_path}")
